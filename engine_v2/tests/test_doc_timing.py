"""Synthetic-only verification of the per-document timing tool."""
from dataclasses import asdict
from functools import lru_cache
import json
from pathlib import Path

import pytest

from engine_v2.tools import doc_timing as tool

SENTINEL = '가짜이름'


# ---------------------------------------------------------------- helpers


def text_pdf(path):
    from engine_v2.tests.nhis_form_samples import text_pdf as acquisition
    return acquisition(path, name=SENTINEL)


def _image_page(document, source_page):
    import pymupdf
    pix = source_page.get_pixmap(dpi=100)
    page = document.new_page(width=source_page.rect.width, height=source_page.rect.height)
    page.insert_image(page.rect, pixmap=pix)
    return pymupdf


def image_pdf(path, source, *, append_text=False):
    import pymupdf
    with pymupdf.open(source) as original, pymupdf.open() as document:
        _image_page(document, original[0])
        if append_text:
            document.insert_pdf(original)
        document.save(path)
    return path


def encrypted_pdf(path, source):
    import pymupdf
    with pymupdf.open(source) as document:
        document.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='u', owner_pw='o')
    return path


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / 'FAKE-input'
    (root / 'person-A').mkdir(parents=True)
    text = text_pdf(root / 'person-A' / 'secret-text.pdf')
    image_pdf(root / 'person-A' / 'secret-image.pdf', text)
    image_pdf(root / 'person-A' / 'secret-later.pdf', text, append_text=True)
    encrypted_pdf(root / 'person-A' / 'secret-locked.pdf', text)
    (root / 'person-A' / 'secret-broken.pdf').write_bytes(b'%PDF-1.7 not really')
    return root


@pytest.fixture
def fake_ocr(monkeypatch):
    from engine_v2.pipeline import ocr as v2ocr
    calls = []

    def recognize(png, size):
        calls.append(size)
        return []
    monkeypatch.setitem(v2ocr.ENGINES, 'own', recognize)
    monkeypatch.setattr(tool, 'own_available', lambda: True)
    return calls


def rows(out):
    return [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]


def row(key='0' * 16, repeat=1, total=1.0, phase='measure', form='NHIS_PAYMENT', text_layer='TEXT', pages=1,
        code='NONE', decision='PASS', later=0, ocr_pages=0, text_pages=1, tier='localocr'):
    seconds = {name: 0.0 for name in tool.STAGES}
    seconds['other'] = total
    seconds['total'] = total
    return tool.validate_row(dict(
        schema_version=tool.VERSION, key=key, engine='own', phase=phase, repeat=repeat, code=code, form=form,
        text_layer=text_layer, pages=pages, page_bin=tool.page_bin(pages), first_image_later_text=later,
        tier=tier, decision=decision, ocr_pages=ocr_pages, text_pages=text_pages, cold_start=0.0,
        seconds=seconds, reasons=[]))


def meta(repeat=1):
    return dict(options=dict(repeat=repeat, warmup=3, sample=None, limit=None, strata_basis='NONE'),
                counts=dict(selected=0), cold_start=None)


def line(text, prefix):
    return [item for item in text.splitlines() if item.startswith(prefix + ' own ')]


# ---------------------------------------------------------------- statistics


def test_percentiles_use_linear_interpolation():
    values = [4.0, 1.0, 3.0, 2.0]
    assert tool.quantile(values, .5) == pytest.approx(2.5)
    assert tool.quantile(values, .9) == pytest.approx(3.7)
    assert tool.quantile(values, .95) == pytest.approx(3.85)
    stats = tool.describe(values)
    assert (stats['n'], stats['mean'], stats['median'], stats['max']) == (4, 2.5, 2.5, 4.0)
    assert tool.describe([]) == dict(n=0, mean=None, median=None, p90=None, p95=None, max=None)


def test_target_flags_include_the_boundary():
    assert tool.target_flags(dict(mean=2.5, p95=5.0)) == ('O', 'O')
    assert tool.target_flags(dict(mean=2.5001, p95=5.0001)) == ('X', 'X')
    assert tool.target_flags(dict(mean=None, p95=None)) == ('NA', 'NA')


def test_repeats_use_the_per_document_median_and_report_spread():
    data = [row(key='a' * 16, repeat=r, total=t) for r, t in ((1, 1.0), (2, 3.0), (3, 2.0))]
    data += [row(key='b' * 16, repeat=r, total=t) for r, t in ((1, 4.0), (2, 4.0), (3, 8.0))]
    text = tool.summarize(data, meta(repeat=3))
    # medians 2.0 and 4.0 → mean 3.0
    assert line(text, 'OVERALL') == ['OVERALL own 2 3.000 3.000 3.800 3.900 4.000']
    # spreads 3.0 and 2.0 → median 2.5, p90 2.9
    assert line(text, 'REPEAT') == ['REPEAT own 3 2 2.500 2.900']
    assert tool.spread([1.0]) is None and tool.spread([0.0, 1.0]) is None


def test_warmup_runs_are_recorded_separately_and_never_enter_statistics():
    data = [row(key='a' * 16, phase='warmup', repeat=0, total=99.0), row(key='a' * 16, total=1.0)]
    text = tool.summarize(data, meta())
    assert line(text, 'OVERALL') == ['OVERALL own 1 1.000 1.000 1.000 1.000 1.000']
    assert line(text, 'WARMUP') == ['WARMUP own 1 99.000 99.000']
    assert line(text, 'TARGET') == ['TARGET own MEAN_LE_2_5S O', 'TARGET own P95_LE_5S O']


def test_summary_groups_slow_forms_and_first_page_image_counts():
    data = [row(key=f'{i:016x}', total=float(i + 1), form='RESIDENT_ABSTRACT' if i < 2 else 'NHIS_PAYMENT',
                pages=i + 1, text_layer='MIXED' if i == 3 else 'TEXT', later=int(i == 3),
                decision='NEEDS_REVIEW' if i == 3 else 'PASS', ocr_pages=int(i == 3), text_pages=1)
            for i in range(4)]
    text = tool.summarize(data, meta())
    assert line(text, 'SLOW_FORM') == ['SLOW_FORM own 1 NHIS_PAYMENT 2 3.500 3.950 70.000',
                                       'SLOW_FORM own 2 RESIDENT_ABSTRACT 2 1.500 1.950 30.000']
    assert 'BY_PAGES own 3+ 2 3.500 3.500 3.900 3.950 4.000' in text
    assert 'BY_TEXT_LAYER own MIXED 1 4.000 4.000 4.000 4.000 4.000' in text
    assert 'FIRST_PAGE_IMAGE_LATER_TEXT own docs 1' in text
    assert 'FIRST_PAGE_IMAGE_LATER_TEXT own status NEEDS_REVIEW 1' in text
    assert line(text, 'PAGES') == ['PAGES own 4 1 10']


# ---------------------------------------------------------------- timer and sampling


def test_stage_timer_keeps_nested_stage_time_exclusive():
    ticks = iter([0.0, 1.0, 3.0, 6.0])
    timer = tool.StageTimer(clock=lambda: next(ticks))
    timer.active = True
    with timer.stage('extract'):        # 0 → 6
        with timer.stage('classify'):   # 1 → 3
            pass
    assert timer.totals['extract'] == pytest.approx(4.0)
    assert timer.totals['classify'] == pytest.approx(2.0)
    timer.active = False
    with timer.stage('ocr'):
        pass
    assert timer.totals['ocr'] == 0.0


def test_same_name_nested_stages_unwind_by_identity():
    ticks = iter([0.0, 1.0, 2.0, 4.0, 7.0, 8.0])
    timer = tool.StageTimer(clock=lambda: next(ticks))
    timer.active = True
    with timer.stage('extract'):            # 0 → 8
        with timer.stage('extract'):        # 1 → 7
            with timer.stage('classify'):   # 2 → 4
                pass
    assert timer.stack == []
    assert timer.totals['extract'] == pytest.approx(6.0)
    assert timer.totals['classify'] == pytest.approx(2.0)


def test_model_load_on_cache_miss_is_cold_start_and_removed_from_the_stage():
    clock = iter([0.0, 1.0, 5.0, 6.0, 10.0, 10.5, 11.0, 12.0])
    timer = tool.StageTimer(clock=lambda: next(clock))
    timer.active, timer.phase = True, 'warmup'

    @lru_cache(maxsize=1)
    def sessions():
        return 'model'
    wrapped = tool._wrap_sessions(timer, sessions)
    with timer.stage('ocr'):            # 0 → 6, model load 1 → 5
        wrapped()
    assert timer.cold_model_load == pytest.approx(4.0) and timer.cold_phase == 'warmup'
    assert timer.excluded == pytest.approx(4.0)
    assert timer.totals['ocr'] == pytest.approx(2.0)
    with timer.stage('ocr'):            # cached call: nothing excluded
        wrapped()
    assert timer.excluded == pytest.approx(4.0)


def test_own_threads_reads_the_loaded_session_options(monkeypatch):
    from engine_v2.pipeline.ocr import own

    class Options:
        intra_op_num_threads, inter_op_num_threads = 2, 1

    class Session:
        def get_session_options(self):
            return Options()

    @lru_cache(maxsize=1)
    def sessions():
        return Session(), None, []
    monkeypatch.setattr(own, 'sessions', sessions)
    assert tool.own_threads() == dict(intra=None, inter=None, loaded='X')
    sessions()
    assert tool.own_threads() == dict(intra=2, inter=1, loaded='O')


def test_stratified_sample_is_deterministic_and_keeps_every_stratum():
    strata = {'A': [f'a{i}' for i in range(80)], 'B': [f'b{i}' for i in range(15)], 'C': ['c0']}
    first = tool.stratified_sample(strata, 20, 7)
    assert first == tool.stratified_sample(strata, 20, 7)
    assert len(first) == 20 and any(k.startswith('c') for k in first) and any(k.startswith('b') for k in first)
    assert tool.allocate({'A': 80, 'B': 15, 'C': 1}, 20) == {'A': 16, 'B': 3, 'C': 1}
    assert tool.allocate({'A': 3, 'B': 2}, 1) == {'A': 1, 'B': 0}
    assert tool.allocate({'A': 3}, 10) == {'A': 3}


def test_inspect_counts_encrypted_open_errors_and_text_layer_classes(corpus):
    found = {path.stem: tool.inspect(path) for path in sorted((corpus / 'person-A').iterdir())}
    assert found['secret-locked'] == dict(code='ENCRYPTED')
    assert found['secret-broken'] == dict(code='OPEN_ERROR')
    assert found['secret-text'] == dict(code='NONE', pages=1, text_layer='TEXT', first_image_later_text=0)
    assert found['secret-image'] == dict(code='NONE', pages=1, text_layer='NONE', first_image_later_text=0)
    assert found['secret-later'] == dict(code='NONE', pages=2, text_layer='MIXED', first_image_later_text=1)


# ---------------------------------------------------------------- production equivalence


def test_wrappers_do_not_change_production_results(tmp_path, monkeypatch):
    from demo.backend.ocr import read_document
    from demo.backend.upload_assessment import assess_upload
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    path = text_pdf(tmp_path / 'sample.pdf')
    req = tool.requirement('NHIS_ACQUISITION_LOSS')

    def once():
        ocr = read_document(str(path), None)
        _, checked = assess_upload(path, req, identity=None, reader=lambda *_: ocr)
        state = asdict(ocr)
        state.pop('elapsed_ms')
        return state, checked.status, [asdict(f) for f in checked.findings]

    plain = once()
    timer = tool.StageTimer()
    with tool.instrument(timer):
        timer.active = True
        wrapped = once()
        timer.active = False
    assert wrapped == plain
    assert plain[0]['detected_doc_type'] is not None
    assert timer.totals['text_layer'] > 0 and timer.totals['extract'] > 0 and timer.totals['evidence'] > 0
    assert timer.text_pages >= 1 and timer.ocr_calls == 0


# ---------------------------------------------------------------- CLI


def test_cli_end_to_end_records_value_free_outputs(corpus, tmp_path, fake_ocr, capsys):
    out = tmp_path / 'FAKE-output' / 'run1'
    assert tool.main(['--root', str(corpus), '--out', str(out), '--repeat', '2', '--warmup', '1']) == 0
    printed = capsys.readouterr().out
    summary = (out / 'summary_brief.txt').read_text()
    recorded = rows(out)
    assert {r['phase'] for r in recorded} == {'warmup', 'measure', 'skipped'}
    assert sum(r['phase'] == 'warmup' for r in recorded) == 1
    assert sum(r['phase'] == 'measure' for r in recorded) == 6        # 3 documents × 2 repeats
    assert 'SKIP ENCRYPTED 1' in summary and 'SKIP OPEN_ERROR 1' in summary
    assert 'ERROR PROCESSING_ERROR 0' in summary
    assert line(summary, 'OVERALL')[0].split()[2] == '3'
    assert 'FIRST_PAGE_IMAGE_LATER_TEXT own docs 1' in summary
    # Production (11-18 O1): an undecided image document and the image-first document with a later
    # text page are re-read from 300 dpi renderings once. The fake engine returns no words, so both
    # stay unclassified: image 1 embedded + 1 rendered page, image-first 2 rendered pages.
    assert line(summary, 'PAGES') == ['PAGES own 1 4 4']
    warm = next(r for r in recorded if r['phase'] == 'warmup')
    assert len(fake_ocr) == 8 + warm['ocr_pages']
    later = [r for r in recorded if r['first_image_later_text'] == 1 and r['phase'] == 'measure']
    assert {(r['ocr_pages'], r['tier'], r['decision']) for r in later} == {(2, 'none', 'NOT_ASSESSED')}
    assert 'TARGET own MEAN_LE_2_5S' in summary and 'COLD_START own' in summary
    meta = json.loads((out / 'run.json').read_text())
    assert meta['counts'] == dict(inventory_pdf=5, selected=5, skipped=2)
    assert meta['options']['external_ocr_disabled'] == 'O'
    assert meta['environment']['finished'] is not None
    for text in (printed, summary, (out / 'run.json').read_text()):
        assert str(tmp_path) not in text and 'secret' not in text and 'person-A' not in text
        assert SENTINEL not in text
        assert not any(r['key'] in text for r in recorded)
    assert all(SENTINEL not in json.dumps(r, ensure_ascii=False) for r in recorded)


def test_out_exists_stops_before_writing(corpus, tmp_path, fake_ocr, capsys):
    out = tmp_path / 'existing'
    out.mkdir()
    assert tool.main(['--root', str(corpus), '--out', str(out)]) == 2
    assert capsys.readouterr().out == 'ERROR OUT_EXISTS\n'
    assert list(out.iterdir()) == []


@pytest.mark.parametrize('extra', [['--engines', 'applevision'], ['--repeat', '0'], ['--sample', '0'],
                                   ['--strata-from', 'x'], ['--unknown']])
def test_argument_errors_print_only_a_code(corpus, tmp_path, extra, capsys):
    assert tool.main(['--root', str(corpus), '--out', str(tmp_path / 'o'), *extra]) == 2
    assert capsys.readouterr().out == 'ERROR ARGUMENT_ERROR\n'
    assert not (tmp_path / 'o').exists()


def test_sample_uses_previous_forms_and_rejects_invalid_strata(corpus, tmp_path, fake_ocr, capsys):
    first = tmp_path / 'first'
    assert tool.main(['--root', str(corpus), '--out', str(first), '--warmup', '0']) == 0
    second = tmp_path / 'second'
    assert tool.main(['--root', str(corpus), '--out', str(second), '--sample', '2', '--strata-from', str(first),
                      '--warmup', '0']) == 0
    meta = json.loads((second / 'run.json').read_text())
    assert meta['options']['strata_basis'] == 'FORM' and meta['counts']['selected'] == 2
    capsys.readouterr()
    assert tool.main(['--root', str(corpus), '--out', str(tmp_path / 'third'), '--sample', '2',
                      '--strata-from', str(tmp_path / 'missing')]) == 2
    assert capsys.readouterr().out == 'ERROR STRATA_INVALID\n'


def test_missing_input_and_overlap_are_codes(corpus, tmp_path, fake_ocr, capsys):
    assert tool.main(['--root', str(tmp_path / 'missing'), '--out', str(tmp_path / 'o')]) == 2
    assert tool.main(['--root', str(corpus), '--out', str(corpus / 'inside')]) == 2
    assert capsys.readouterr().out == 'ERROR INPUT_UNAVAILABLE\nERROR INPUT_OUTPUT_OVERLAP\n'


def test_validate_row_rejects_paths_and_unknown_codes():
    good = row()
    with pytest.raises(Exception):
        tool.validate_row({**good, 'key': '/Users/x.pdf'})
    with pytest.raises(Exception):
        tool.validate_row({**good, 'form': '주민등록초본'})
    with pytest.raises(Exception):
        tool.validate_row({**good, 'extra': 1})
