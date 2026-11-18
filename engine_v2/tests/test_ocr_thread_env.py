"""OWN_OCR_INTRA_THREADS / OWN_OCR_PAGE_WORKERS: defaults, overrides, invalid values, recording (synthetic)."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from engine_v2.pipeline.ocr import own
from engine_v2.tests.test_doc_timing import corpus, fake_ocr, rows  # noqa: F401 - fixtures
from engine_v2.tools import doc_timing as tool

REPO = Path(__file__).resolve().parents[2]
NAMES = ('OWN_OCR_INTRA_THREADS', 'OWN_OCR_PAGE_WORKERS')
PATHLIKE = '/Users/secret-person/x.pdf'


def _import_own(**env):
    """Fresh interpreter: the module-level settings exactly as a new process reads them."""
    clean = {k: v for k, v in os.environ.items() if k not in NAMES}
    done = subprocess.run(
        [sys.executable, '-B', '-c',
         'from engine_v2.pipeline.ocr import own; print(own.INTRA_OP_THREADS, own.MAX_PAGE_WORKERS)'],
        cwd=REPO, env={**clean, **env}, capture_output=True, text=True, timeout=60, check=True)
    return done.stdout.split(), done.stderr.splitlines()


# ---------------------------------------------------------------- parsing


def test_unset_and_empty_keep_the_default_silently(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.delenv('OWN_OCR_X', raising=False)
    assert own._env_count('OWN_OCR_X', 2) == 2
    for raw in ('', '  '):
        monkeypatch.setenv('OWN_OCR_X', raw)
        assert own._env_count('OWN_OCR_X', 2) == 2
    assert caplog.records == []


@pytest.mark.parametrize('raw, expected', [('1', 1), ('3', 3), (' 8 ', 8), ('16', 16)])
def test_positive_integers_are_used(monkeypatch, caplog, raw, expected):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.setenv('OWN_OCR_X', raw)
    assert own._env_count('OWN_OCR_X', 2) == expected
    assert caplog.records == []


@pytest.mark.parametrize('raw', ['0', '00', '-1', '-4', 'abc', '2.5', '+3', '3_0', '٣', '1e2', '9999999',
                                 PATHLIKE])
def test_invalid_values_fall_back_with_one_warning_line(monkeypatch, caplog, raw):
    caplog.set_level(logging.WARNING, logger=own.__name__)
    monkeypatch.setenv('OWN_OCR_X', raw)
    assert own._env_count('OWN_OCR_X', 4) == 4
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert message == 'OWN_OCR_X is not a positive integer; using default 4'
    assert '\n' not in message


# ---------------------------------------------------------------- module settings in a new process


def test_no_environment_gives_2_and_4():
    values, stderr = _import_own()
    assert values == ['2', '4'] and stderr == []


@pytest.mark.parametrize('intra, workers', [('4', '2'), ('1', '4'), ('2', '1'), ('3', '6')])
def test_each_variable_sets_its_value(intra, workers):
    assert _import_own(OWN_OCR_INTRA_THREADS=intra)[0] == [intra, '4']
    assert _import_own(OWN_OCR_PAGE_WORKERS=workers)[0] == ['2', workers]
    values, stderr = _import_own(OWN_OCR_INTRA_THREADS=intra, OWN_OCR_PAGE_WORKERS=workers)
    assert values == [intra, workers] and stderr == []


@pytest.mark.parametrize('bad', ['0', '-2', 'many', PATHLIKE])
def test_invalid_values_give_defaults_and_one_line_each(bad):
    values, stderr = _import_own(OWN_OCR_INTRA_THREADS=bad, OWN_OCR_PAGE_WORKERS=bad)
    assert values == ['2', '4']
    assert stderr == ['OWN_OCR_INTRA_THREADS is not a positive integer; using default 2',
                      'OWN_OCR_PAGE_WORKERS is not a positive integer; using default 4']


# ---------------------------------------------------------------- worker budget


@pytest.mark.parametrize('intra, workers, cap', [(2, 4, 4), (4, 2, 2), (1, 4, 4), (2, 1, 1), (4, 4, 2)])
def test_page_worker_cap_follows_the_settings(monkeypatch, intra, workers, cap):
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 8)
    monkeypatch.setattr(own, 'INTRA_OP_THREADS', intra)
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', workers)
    assert own.page_workers(9) == cap and own.page_workers(9) * intra <= 8


def test_one_page_worker_reads_sequentially(monkeypatch):
    from engine_v2.pipeline import ocr
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', 1)
    monkeypatch.setattr(own, 'page_sessions', lambda slot: (_ for _ in ()).throw(AssertionError(slot))
                        if slot else None)
    threads = []
    monkeypatch.setitem(ocr.ENGINES, 'own', lambda png, size: threads.append(
        __import__('threading').current_thread().name) or [])
    images = [(b'png', (10, 10))] * 3
    assert own.prepare_page_workers(len(images)) == 1
    for read in ocr.run_ocr_pages('own', images):
        read()
    assert len(threads) == 3 and not any(name.startswith('own-page') for name in threads)


# ---------------------------------------------------------------- doc_timing records the values in force


def _run(corpus, out, *extra):
    assert tool.main(['--root', str(corpus), '--out', str(out), '--warmup', '0', *extra]) == 0
    return rows(out), json.loads((out / 'run.json').read_text()), (out / 'summary_brief.txt').read_text()


@pytest.mark.parametrize('intra, workers, cap', [(2, 4, 4), (4, 2, 2), (1, 4, 4), (2, 1, 1)])
def test_doc_timing_records_settings_in_rows_and_summary(corpus, tmp_path, fake_ocr, monkeypatch, capsys,
                                                         intra, workers, cap):
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 8)
    monkeypatch.setattr(own, 'INTRA_OP_THREADS', intra)
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', workers)
    recorded, meta, summary = _run(corpus, tmp_path / 'FAKE-output' / 'run')
    printed = capsys.readouterr().out
    assert recorded and {(r['schema_version'], r['intra_threads'], r['page_workers']) for r in recorded} == {
        (3, intra, workers)}
    assert meta['options']['ocr_threads'] == dict(intra_threads=intra, page_workers=workers, page_workers_cap=cap)
    expected = f'OCR_THREADS own {intra} {workers} {cap}'
    assert expected in summary.splitlines() and expected in printed.splitlines()
    for text in (printed, summary, json.dumps(meta), json.dumps(recorded, ensure_ascii=False)):
        assert str(tmp_path) not in text and 'secret' not in text and 'person-A' not in text
        assert '.pdf' not in text


def test_rows_reject_missing_or_invalid_settings():
    from engine_v2.tests.test_doc_timing import row
    good = row()
    for bad in ({k: v for k, v in good.items() if k != 'page_workers'}, {**good, 'intra_threads': 0},
                {**good, 'page_workers': '4'}, {**good, 'intra_threads': True}):
        with pytest.raises(Exception):
            tool.validate_row(bad)


@pytest.mark.parametrize('strata', [False, True])
def test_sample_selects_the_same_documents_for_a_seed_whatever_the_settings(
        corpus, tmp_path, fake_ocr, monkeypatch, capsys, strata):
    extra = ['--sample', '2', '--seed', '20261118']
    if strata:
        _run(corpus, tmp_path / 'full')
        extra += ['--strata-from', str(tmp_path / 'full')]
    picked = []
    for number, (intra, workers) in enumerate([(2, 4), (4, 2), (1, 4), (2, 1), (2, 4)]):
        monkeypatch.setattr(own, 'INTRA_OP_THREADS', intra)
        monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', workers)
        recorded, meta, _ = _run(corpus, tmp_path / f'run{number}', *extra)
        assert meta['options']['strata_basis'] == ('FORM' if strata else 'PAGES_TEXT')
        assert meta['counts']['selected'] == 2
        picked.append(sorted({r['key'] for r in recorded}))
    assert all(keys == picked[0] for keys in picked) and len(picked[0]) == 2
    capsys.readouterr()


# ---------------------------------------------------------------- readers accept formats 1, 2 and 3


def _formats(**fields):
    """The same measured row in formats 3, 2 and 1."""
    from engine_v2.tests.test_doc_timing import row
    v3 = row(**fields)
    v2 = {k: v for k, v in v3.items() if k not in ('intra_threads', 'page_workers')}
    v2['schema_version'] = 2
    v1 = {k: v for k, v in v2.items() if k != 'reasons'}
    v1['schema_version'] = 1
    return {3: v3, 2: tool.validate_row(v2), 1: tool.validate_row(v1)}


def _write(path, rows_):
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows_))
    return path


def test_classify_recovery_diag_compare_reads_format_3_and_older_rows(tmp_path, capsys):
    from engine_v2.tools import classify_recovery_diag as diag
    a = _formats(key='a' * 16, form='NHIS_PAYMENT', decision='PASS')
    b = _formats(key='b' * 16, form='RESIDENT_ABSTRACT', decision='PASS')
    a_after = _formats(key='a' * 16, form='X', decision='NOT_ASSESSED')
    v3_before = _write(tmp_path / 'v3-before.jsonl', [a[3], b[3]])
    v3_after = _write(tmp_path / 'v3-after.jsonl', [a_after[3], b[3]])
    mixed = _write(tmp_path / 'mixed.jsonl', [a[1], b[2]])
    for before, after in ((v3_before, v3_after), (mixed, v3_after), (v3_after, mixed)):
        capsys.readouterr()
        assert diag.main(['compare', '--before', str(before), '--after', str(after)]) == 0
        printed = capsys.readouterr().out
        assert 'COMPARE 2 2 2 0 0' in printed and 'CHANGED decision form either 1 1 1' in printed
        assert str(tmp_path) not in printed
    measured, _ = diag._timing_rows(_write(tmp_path / 'all.jsonl', [a[1], b[2], {**a[3], 'repeat': 2}]))
    assert sorted(measured) == ['a' * 16, 'b' * 16]
    bad = _write(tmp_path / 'bad.jsonl', [{**a[3], 'schema_version': 4}])
    assert diag.main(['compare', '--before', str(bad), '--after', str(v3_after)]) == 2


def test_strata_from_reads_a_format_3_run(corpus, tmp_path, fake_ocr, capsys):
    recorded, meta, _ = _run(corpus, tmp_path / 'full')
    assert meta['schema_version'] == 3 and {r['schema_version'] for r in recorded} == {3}
    forms = tool.load_strata(tmp_path / 'full')
    assert forms and set(forms) <= {r['key'] for r in recorded}
    capsys.readouterr()
