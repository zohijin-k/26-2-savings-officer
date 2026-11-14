"""Synthetic-only CLI, continuation and disclosure-boundary verification."""
from copy import deepcopy
import io
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from engine_v2.tools import ocr_baseline as tool
from engine_v2.tools import ocr_baseline_runtime as runtime

SENTINEL = 'SYNTHETIC_PRIVATE_SENTINEL_483790'


@pytest.fixture
def corpus(tmp_path):
    root, out = tmp_path / 'FAKE-input', tmp_path / 'FAKE-output'
    root.mkdir()
    return root, out


def make_pdf(path, texts=None):
    import pymupdf
    if texts is None:
        from engine_v2.tests.nhis_form_samples import text_pdf
        return text_pdf(path, name='가짜이름')
    with pymupdf.open() as doc:
        for text in texts:
            page = doc.new_page()
            writer = pymupdf.TextWriter(page.rect)
            writer.append((30, 50), text, font=pymupdf.Font('cjk'), fontsize=8)
            writer.write_text(page)
        doc.save(path)
    return path


def records(out):
    path = out / 'results.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def invoke(root, out, *args):
    return tool.main(['--root', str(root), '--out', str(out), '--variants', 'clean', *args])


def fake_ocr(monkeypatch, source):
    import pymupdf
    from engine_v2.pipeline.ocr import OcrResult
    with pymupdf.open(source) as doc:
        _, truth = runtime.reference_page(doc[0], 0)
    def recognize(engine, page):
        return OcrResult(engine, deepcopy(truth)), deepcopy(truth), dict(
            ocr=.01, detection=.003 if engine == 'own' else None,
            recognition=.004 if engine == 'own' else None, initialization=0.0,
            residual=.003, observer=0.0, cold=0, intra_threads=2 if engine == 'own' else None,
            inter_threads=1 if engine == 'own' else None, workers=1)
    monkeypatch.setattr(runtime, 'recognize', recognize)
    return truth


def no_disclosure(out, capfd):
    captured = capfd.readouterr()
    assert SENTINEL not in captured.out + captured.err
    assert captured.err == ''
    for path in out.iterdir():
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()


def test_complete_reference_fields_and_resume(corpus, monkeypatch, capfd):
    root, out = corpus
    source = make_pdf(root / 'neutral.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out, '--engines', 'own', 'applevision') == 0
    row = records(out)[0]
    page = row['pages'][0]
    assert row['page_count'] == 1 and row['code'] == 'NONE'
    assert page['type'] == 'NHIS_ACQUISITION_LOSS'
    assert page['exclusion'] == 'NONE'
    assert len(page['measurements']) == 2
    for item in page['measurements']:
        assert item['metrics']['cer']['rate'] == 0
        assert item['metrics']['words']['f1'] == 1
        assert item['fields']['성명']['match'] == 1
        assert item['fields']['성명']['eligible'] == 1
        assert item['seconds']['total'] >= .01
    before = (out / 'results.jsonl').read_bytes()
    monkeypatch.setattr(tool, 'process_file', lambda *a: pytest.fail('completed content reopened'))
    assert invoke(root, out, '--engines', 'own', 'applevision') == 0
    assert (out / 'results.jsonl').read_bytes() == before
    assert str(root) not in (out / 'run.json').read_text()
    assert '가짜이름' not in before.decode()
    assert (out / 'summary.json').is_file() and (out / 'summary.txt').is_file()
    no_disclosure(out, capfd)


def test_limit_attempts_unfinished_documents_and_full_resumes(corpus, monkeypatch):
    root, out = corpus
    for name in ('a.pdf', 'b.pdf', 'c.pdf'):
        make_pdf(root / name)
    fake_ocr(monkeypatch, root / 'a.pdf')
    assert invoke(root, out, '--limit', '1') == 0
    assert [r['id'] for r in records(out)] == ['a.pdf']
    before = (out / 'results.jsonl').read_bytes()
    assert invoke(root, out, '--limit', '1') == 0
    assert [r['id'] for r in records(out)] == ['a.pdf', 'b.pdf']
    assert invoke(root, out) == 0
    assert len(records(out)) == 3
    assert (out / 'results.jsonl').read_bytes().startswith(before)


def test_ids_selection_preserves_spaces_and_never_reads_unselected(corpus, monkeypatch, capfd):
    root, out = corpus
    source = make_pdf(root / '한 글.PDF')
    (root / 'not-selected.pdf').write_bytes(b'not a document')
    (root / 'ignored.png').write_bytes(b'not opened')
    ids = root.parent / 'FAKE-selection.txt'
    ids.write_text('한 글.PDF\r\n한 글.PDF\n../outside.pdf\nmissing.pdf\nwrong.txt\n')
    fake_ocr(monkeypatch, source)
    original = tool.process_file
    calls = []
    def process(path, *args):
        assert path == source
        calls.append(path)
        return original(path, *args)
    monkeypatch.setattr(tool, 'process_file', process)
    assert invoke(root, out, '--ids', str(ids)) == 0
    assert len(calls) == 1 and records(out)[0]['id'] == '한 글.PDF'
    output = capfd.readouterr().out
    assert 'duplicates 1' in output and 'outside_root 1' in output
    assert 'missing 1' in output and 'invalid 1' in output
    assert '한 글' not in output and 'outside.pdf' not in output


@pytest.mark.parametrize('bad', ['--limit', '--engines', '--variants'])
def test_invalid_arguments_never_echo_or_create_output(corpus, capfd, bad):
    root, out = corpus
    value = '0' if bad == '--limit' else SENTINEL
    assert invoke(root, out, bad, value) == 2
    assert not out.exists()
    assert capfd.readouterr().out == ''


def test_exclusions_are_page_local_and_encryption_is_document_local(corpus, monkeypatch):
    import pymupdf
    root, out = corpus
    reference = make_pdf(root / 'reference.pdf')
    fake_ocr(monkeypatch, reference)
    with pymupdf.open(reference) as doc:
        with pymupdf.open() as mixed:
            mixed.insert_pdf(doc)
            mixed.new_page()
            short = mixed.new_page()
            short.insert_text((30, 30), 'short')
            unknown = mixed.new_page()
            unknown.insert_text((30, 30), 'SYNTHETIC UNKNOWN DOCUMENT ONLY ' * 4, fontsize=6)
            mixed.save(root / 'mixed.pdf')
        doc.save(root / 'encrypted.pdf', encryption=pymupdf.PDF_ENCRYPT_AES_256,
                 owner_pw='FAKE-owner', user_pw='FAKE-user')
    assert invoke(root, out) == 0
    saved = {r['id']: r for r in records(out)}
    assert saved['encrypted.pdf']['code'] == 'ENCRYPTED'
    assert saved['encrypted.pdf']['page_count'] is None
    assert [p['exclusion'] for p in saved['mixed.pdf']['pages']] == [
        'NONE', 'NO_TEXT_LAYER', 'SHORT_TEXT_LAYER', 'CLASSIFICATION_FAILED']
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['excluded_pages']['NO_TEXT_LAYER'] == 1
    assert summary['inaccessible_page_count'] == 1


@pytest.mark.parametrize('text,code', [('a' * 99 + '\ufffd', 'BROKEN_TEXT_LAYER'),
                                     ('a' * 95 + '\ue000' * 5, 'BROKEN_TEXT_LAYER'),
                                     ('a' * 99 + '\ue000', 'NONE'),
                                     ('a' * 95 + '\x00' * 5, 'BROKEN_TEXT_LAYER')])
def test_quality_thresholds(text, code):
    assert runtime.quality(text, [object()])[0] == code


def test_broken_layer_excluded_before_ocr(corpus, monkeypatch):
    root, out = corpus
    make_pdf(root / 'fake.pdf')
    monkeypatch.setattr(runtime, 'quality', lambda text, words: ('BROKEN_TEXT_LAYER', dict(tool.QUALITY)))
    monkeypatch.setattr(runtime, 'recognize', lambda *a: pytest.fail('excluded page OCR'))
    assert invoke(root, out) == 0
    assert records(out)[0]['pages'][0]['exclusion'] == 'BROKEN_TEXT_LAYER'


def test_missing_engine_and_processing_errors_have_distinct_denominators(corpus, monkeypatch, capfd):
    root, out = corpus
    make_pdf(root / 'fake.pdf')
    def recognize(engine, page):
        if engine == 'applevision':
            raise ImportError(SENTINEL)
        print(SENTINEL)
        logging.error(SENTINEL)
        os.write(2, SENTINEL.encode())
        raise ValueError(SENTINEL)
    monkeypatch.setattr(runtime, 'recognize', recognize)
    assert invoke(root, out, '--engines', 'own', 'applevision') == 1
    items = records(out)[0]['pages'][0]['measurements']
    assert [(i['state'], i['code']) for i in items] == [('ERROR', 'OCR_ERROR'), ('SKIPPED', 'ENGINE_UNAVAILABLE')]
    summary = json.loads((out / 'summary.json').read_text())
    assert sum(g['successful'] for g in summary['groups']) == 0
    no_disclosure(out, capfd)


@pytest.mark.parametrize('attempt', ['write', 'network'])
def test_guard_blocks_even_swallowed_side_effects(corpus, monkeypatch, attempt, capfd):
    root, out = corpus
    make_pdf(root / 'fake.pdf')
    target = root.parent / 'FAKE-forbidden.txt'
    def process(*args):
        try:
            if attempt == 'write':
                target.write_text(SENTINEL)
            else:
                socket.getaddrinfo('localhost', 80)
        except Exception:
            pass
        return tool._blank_document('fake.pdf', page_count=0)
    monkeypatch.setattr(tool, 'process_file', process)
    assert invoke(root, out) == 1
    assert records(out)[0]['code'] == 'PROCESSING_ERROR'
    assert not target.exists()
    no_disclosure(out, capfd)


def test_reference_and_ocr_field_errors_do_not_leak_values(corpus, monkeypatch, capfd):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    original = runtime.extract
    def extract(page, words, engine):
        result, raw = original(page, words, engine)
        raw.update({SENTINEL: SENTINEL, '성명': SENTINEL})
        return result, raw
    monkeypatch.setattr(runtime, 'extract', extract)
    assert invoke(root, out) == 0
    assert records(out)[0]['pages'][0]['measurements'][0]['fields']['성명']['match'] == 1
    no_disclosure(out, capfd)


def test_tail_recovery_and_config_mismatch_do_not_rewrite_completed_rows(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out) == 0
    path = out / 'results.jsonl'
    original = path.read_bytes()
    path.write_bytes(original + b'{"schema_version":')
    # Incompatible engines must reject before tail recovery.
    assert invoke(root, out, '--engines', 'applevision') == 2
    assert path.read_bytes() == original + b'{"schema_version":'
    assert invoke(root, out) == 0
    assert path.read_bytes() == original
    path.write_bytes(original + original)
    assert invoke(root, out) == 2
    assert path.read_bytes() == original + original


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'ids_alias'])
def test_reject_output_aliases_without_mutation(corpus, monkeypatch, kind):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    out.mkdir()
    target = out / 'summary.txt'
    if kind == 'symlink':
        target.symlink_to(source)
    elif kind == 'hardlink':
        os.link(source, target)
    else:
        target.write_text('fake.pdf\n')
    before = source.read_bytes()
    args = ['--ids', str(target)] if kind == 'ids_alias' else []
    assert invoke(root, out, *args) == 2
    assert source.read_bytes() == before
    assert not (out / 'run.json').exists()


def test_summary_read_only_and_does_not_load_backend_or_visit_input(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out) == 0
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()}
    source.unlink()
    root.rmdir()
    code = ("import sys; from engine_v2.tools.ocr_baseline import main; "
            "assert main(['--out',sys.argv[1],'--summarize']) == 0; "
            "assert not any(k.startswith('engine_v2.pipeline') or k.startswith('demo.backend.ocr') for k in sys.modules)")
    result = subprocess.run([sys.executable, '-B', '-c', code, str(out)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode()
    assert b'NHIS_ACQUISITION_LOSS' in result.stdout
    assert b'fake.pdf' not in result.stdout
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()}


def test_schema_rejects_unknown_keys_and_numeric_string_payloads(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out) == 0
    path = out / 'results.jsonl'
    row = records(out)[0]
    row['pages'][0]['measurements'][0]['metrics']['cer']['edits'] = SENTINEL
    path.write_text(json.dumps(row) + '\n')
    before = path.read_bytes()
    assert tool.main(['--out', str(out), '--summarize']) == 2
    assert path.read_bytes() == before


def test_variants_deterministic_in_memory_and_same_seed_on_resume(corpus, monkeypatch):
    import pymupdf
    import numpy as np
    from engine_v2.tools import batch_assess
    root, _ = corpus
    source = make_pdf(root / 'fake.pdf')
    with batch_assess.guarded(), pymupdf.open(source) as doc:
        reference, words = runtime.reference_page(doc[0], 0)
        seed = runtime.page_seed('fake.pdf', 1)
        phone, matrix = runtime.variant_image(doc[0], 'phone', seed, reference.pixel_size)
        same, identical = runtime.variant_image(doc[0], 'phone', seed, reference.pixel_size)
        scan, scan_matrix = runtime.variant_image(doc[0], 'scan', seed, reference.pixel_size)
        clean, identity = runtime.variant_image(doc[0], 'clean', seed, reference.pixel_size)
        assert phone.png == same.png
        assert np.array_equal(matrix, identical)
        assert scan.dpi == 200 and clean.dpi == phone.dpi == 300
        assert scan.pixel_size[0] < clean.pixel_size[0]
        assert np.allclose(identity, np.eye(3))
        assert not np.allclose(matrix, np.eye(3))
        assert runtime.page_seed('fake.pdf', 1) != runtime.page_seed('fake.pdf', 2)
        assert runtime.map_words(words, scan_matrix)[0].bbox_px[0] < words[0].bbox_px[0]


def test_original_adapter_mask_observer_restores_and_preserves_masked_result(monkeypatch):
    from engine_v2.pipeline import ocr
    from engine_v2.pipeline.ocr import OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    original = ocr.mask_words
    words = [OcrWord('900101-1234567', .99, (1, 1, 150, 20))]
    def adapter(png, size):
        return ocr.mask_words(deepcopy(words))
    monkeypatch.setitem(ocr.ENGINES, 'applevision', adapter)
    page = PageImage(0, PageSource.RENDER, (595, 842), png=b'FAKE', pixel_size=(200, 200))
    result, raw, timing = runtime.recognize('applevision', page)
    assert raw[0].text == '900101-1234567'
    assert result.words[0].text == '900101-1******'
    assert ocr.mask_words is original
    assert timing['detection'] is None
    def failure(*args):
        raise ValueError(SENTINEL)
    monkeypatch.setitem(ocr.ENGINES, 'applevision', failure)
    with pytest.raises(ValueError):
        runtime.recognize('applevision', page)
    assert ocr.mask_words is original


def test_progress_distinguishes_limit_remaining_from_completed_skips(corpus, monkeypatch, capfd):
    root, out = corpus
    for name in ('a.pdf', 'b.pdf', 'c.pdf'):
        make_pdf(root / name)
    fake_ocr(monkeypatch, root / 'a.pdf')
    assert invoke(root, out, '--limit', '1') == 0
    assert 'completed 1 skipped 0 remaining 2 total 3' in capfd.readouterr().out
    assert invoke(root, out, '--limit', '1') == 0
    assert 'completed 1 skipped 1 remaining 1 total 3' in capfd.readouterr().out


def test_extraction_error_retains_valid_ocr_timing_and_explicit_table_coverage(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    original = runtime.extract
    def extract(page, words, engine):
        if engine != 'text_layer':
            raise ValueError(SENTINEL)
        return original(page, words, engine)
    monkeypatch.setattr(runtime, 'extract', extract)
    assert invoke(root, out) == 1
    item = records(out)[0]['pages'][0]['measurements'][0]
    assert item['code'] == 'EXTRACTION_ERROR'
    assert item['metrics']['cer']['rate'] == 0
    summary = json.loads((out / 'summary.json').read_text())['groups'][0]
    assert summary['successful'] == 0
    assert summary['seconds']['ocr']['count'] == 1
    assert summary['seconds']['ocr']['mean'] == .01
    assert summary['seconds']['extraction']['count'] == 1
    assert summary['attempt_seconds']['count'] == 1
    assert summary['table_unmeasured'] == 1 and summary['table_unavailable'] == 0


def test_numeric_metric_corruption_is_rejected_without_repair(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out) == 0
    row = records(out)[0]
    row['pages'][0]['measurements'][0]['metrics']['cer']['edits'] = .5
    path = out / 'results.jsonl'
    path.write_text(json.dumps(row) + '\n')
    before = path.read_bytes()
    assert invoke(root, out) == 2
    assert path.read_bytes() == before
    assert tool.main(['--out', str(out), '--summarize']) == 2
    assert path.read_bytes() == before


def test_own_timing_and_mask_observers_restore_after_failed_adapter(monkeypatch):
    from functools import lru_cache
    from types import SimpleNamespace
    from engine_v2.pipeline import ocr
    from engine_v2.pipeline.ocr import own
    from engine_v2.pipeline.preprocess import PageImage, PageSource

    class Recognizer:
        def get_session_options(self):
            return SimpleNamespace(intra_op_num_threads=2, inter_op_num_threads=1)
        def run(self, *args, **kwargs):
            return [1]

    @lru_cache(maxsize=1)
    def sessions():
        return object(), Recognizer(), ['A']
    detect = lambda *args, **kwargs: []
    monkeypatch.setattr(own, 'sessions', sessions)
    monkeypatch.setattr(own, '_detect', detect)
    original_mask, original_own_mask = ocr.mask_words, own.mask_words
    def adapter(png, size):
        det, rec, _ = own.sessions()
        own._detect(None, det)
        rec.run(None)
        own.mask_words([])
        raise ValueError(SENTINEL)
    monkeypatch.setitem(ocr.ENGINES, 'own', adapter)
    page = PageImage(0, PageSource.RENDER, (595, 842), png=b'FAKE', pixel_size=(200, 200))
    with pytest.raises(ValueError):
        runtime.recognize('own', page)
    assert own.sessions is sessions and own._detect is detect
    assert own.mask_words is original_own_mask and ocr.mask_words is original_mask


def test_empty_engine_result_has_explicit_population_and_full_detection_misses(corpus, monkeypatch):
    from engine_v2.pipeline.ocr import OcrResult
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    original = runtime.recognize
    def empty(engine, page):
        _, _, seconds = original(engine, page)
        return OcrResult(engine, []), [], seconds
    monkeypatch.setattr(runtime, 'recognize', empty)
    assert invoke(root, out) == 0
    group = json.loads((out / 'summary.json').read_text())['groups'][0]
    assert group['empty_ocr_pages'] == 1
    assert group['metrics']['cer']['rate'] == 1
    assert group['metrics']['lines']['miss_rate'] == 1
    assert group['table_unmeasured'] == 1 and group['table_unavailable'] == 0


def test_changed_ids_can_expand_resume_without_rewriting_completed_records(corpus, monkeypatch):
    root, out = corpus
    for name in ('a.pdf', 'b.pdf'):
        make_pdf(root / name)
    fake_ocr(monkeypatch, root / 'a.pdf')
    ids = root.parent / 'FAKE-selection.txt'
    ids.write_text('b.pdf\n')
    assert invoke(root, out, '--ids', str(ids)) == 0
    assert [row['id'] for row in records(out)] == ['b.pdf']
    before = (out / 'results.jsonl').read_bytes()
    ids.write_text('')
    assert invoke(root, out, '--ids', str(ids)) == 0
    assert (out / 'results.jsonl').read_bytes() == before
    ids.write_text('b.pdf\na.pdf\n')
    assert invoke(root, out, '--ids', str(ids)) == 0
    assert [row['id'] for row in records(out)] == ['b.pdf', 'a.pdf']
    assert (out / 'results.jsonl').read_bytes().startswith(before)


def test_corrupt_pdf_is_terminal_and_does_not_prevent_later_measurement(corpus, monkeypatch):
    root, out = corpus
    (root / 'a.pdf').write_bytes(b'FAKE invalid PDF')
    source = make_pdf(root / 'b.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out) == 1
    rows = records(out)
    assert rows[0]['code'] == 'OPEN_ERROR'
    assert rows[1]['pages'][0]['measurements'][0]['state'] == 'OK'
    before = (out / 'results.jsonl').read_bytes()
    monkeypatch.setattr(tool, 'process_file', lambda *a: pytest.fail('terminal row reopened'))
    assert invoke(root, out) == 1
    assert (out / 'results.jsonl').read_bytes() == before


def test_output_input_overlap_rejected_before_output_creation(corpus):
    root, out = corpus
    assert invoke(root, root / 'FAKE-output') == 2
    assert not (root / 'FAKE-output').exists()


def test_no_service_verdict_or_batch_assessment_called(corpus, monkeypatch):
    from demo.backend import upload_assessment
    root, out = corpus
    source = make_pdf(root / 'fake.pdf')
    fake_ocr(monkeypatch, source)
    def forbidden(*args, **kwargs):
        pytest.fail('service verdict path invoked')
    monkeypatch.setattr(upload_assessment, 'assess_upload', forbidden)
    monkeypatch.setattr(tool.batch, '_assess', forbidden)
    assert invoke(root, out) == 0


def test_source_pdf_sentinel_never_reaches_outputs_or_logs(corpus, monkeypatch, capfd):
    import pymupdf
    root, out = corpus
    source = make_pdf(root / 'neutral.pdf')
    # The PDF is authored by this test above; no stored fixture is inspected.
    with pymupdf.open(source) as document:
        document[0].insert_text((30, 810), SENTINEL, fontsize=8)
        document.saveIncr()
        assert SENTINEL in document[0].get_text()
    truth = fake_ocr(monkeypatch, source)
    assert SENTINEL in ' '.join(word.text for word in truth)
    assert invoke(root, out) == 0
    no_disclosure(out, capfd)
    # A summary includes metric labels and numeric aggregates only.
    assert tool.main(['--out', str(out), '--summarize']) == 0
    no_disclosure(out, capfd)


def test_text_summary_starts_with_compact_cross_group_comparison(corpus, monkeypatch):
    root, out = corpus
    source = make_pdf(root / 'neutral.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out, '--engines', 'own', 'applevision') == 0
    lines = (out / 'summary.txt').read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith('type engine variant attempted successful CER_mean'))
    assert lines[index + 1].startswith('NHIS_ACQUISITION_LOSS applevision clean 1 1 ')
    assert lines[index + 2].startswith('NHIS_ACQUISITION_LOSS own clean 1 1 ')
    assert len(lines[index].split()) == len(lines[index + 1].split()) == 17
    assert any(line.startswith('metrics.height_bins.') for line in lines[index + 3:])
