"""11-19: own OCR threads chosen by page count (model-free; sessions are recorded markers).

Auto (neither OWN_OCR_INTRA_THREADS nor OWN_OCR_PAGE_WORKERS set): a document read one page at a time
uses one intra-4 session (within the CPU count); 2+ pages use separate intra-2 page sessions with up
to 4 pages at once, so workers x 2 never exceeds the logical CPU count. Either variable fixes the
values as before. Swapped readers stay sequential.
"""
import io
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from engine_v2.pipeline import ocr
from engine_v2.pipeline.ocr import own

REPO = Path(__file__).resolve().parents[2]


def _png():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (12, 10), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def loads(monkeypatch):
    """Real session caches over a fake loader: each load returns a marker naming its thread count."""
    loaded = []

    def load(intra_threads=None):
        intra = own.INTRA_OP_THREADS if intra_threads is None else intra_threads
        marker = (f'det-{len(loaded)}-i{intra}', 'rec', [])
        loaded.append(intra)
        return marker
    monkeypatch.setattr(own, '_load_sessions', load)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 8)
    own.sessions.cache_clear()
    own.page_sessions.cache_clear()
    used = []
    monkeypatch.setattr(own, '_detect', lambda image, det: used.append((det, threading.get_ident())) or [])
    yield loaded, used
    own.sessions.cache_clear()
    own.page_sessions.cache_clear()


def _read(pages):
    image = _png()
    return [read() for read in ocr.run_ocr_pages('own', [(image, (12, 10))] * pages)]


def test_one_page_uses_the_intra_4_session(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    _read(1)
    assert loaded == [4] and [det for det, _ in used] == ['det-0-i4']
    assert used[0][1] == threading.get_ident()


def test_several_pages_use_intra_2_page_sessions_concurrently(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    _read(3)
    assert loaded == [2, 2, 2]  # slot 0 is its own page session, not the intra-4 one
    assert len(used) == 3 and {det for det, _ in used} <= {'det-0-i2', 'det-1-i2', 'det-2-i2'}
    assert threading.get_ident() not in {thread for _, thread in used}
    _read(1)
    assert loaded == [2, 2, 2, 4]  # a later one-page document loads the single session once
    _read(5)
    assert loaded == [2, 2, 2, 4, 2]  # a fourth worker slot; never more than four
    assert own.page_workers(9) * own.INTRA_OP_THREADS <= 8


@pytest.mark.parametrize('cores, single, workers', [(1, 1, 1), (2, 2, 1), (4, 4, 2), (8, 4, 4), (16, 4, 4)])
def test_thread_budget_stays_within_the_cores(monkeypatch, cores, single, workers):
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: cores)
    assert own.single_intra_threads() == single and own.page_workers(9) == workers
    assert single <= cores and workers * own.INTRA_OP_THREADS <= max(cores, own.INTRA_OP_THREADS)


def test_one_worker_reads_sequentially_on_the_single_session(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 2)
    _read(3)
    assert loaded == [2] and [det for det, _ in used] == ['det-0-i2'] * 3
    assert {thread for _, thread in used} == {threading.get_ident()}


def test_fixed_values_share_slot_0_as_before(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', False)
    monkeypatch.setattr(own, 'INTRA_OP_THREADS', 3)
    _read(1)
    _read(2)
    assert loaded == [3, 3]  # single session (slot 0) + one extra page session, both intra 3
    assert len(used) == 3 and used[0][0] == 'det-0-i3' and {det for det, _ in used} <= {'det-0-i3', 'det-1-i3'}
    assert own.single_intra_threads() == 3


def test_swapped_reader_stays_sequential_in_auto(monkeypatch):
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own, 'prepare_page_workers', lambda pages: (_ for _ in ()).throw(AssertionError))
    calls = []
    monkeypatch.setitem(ocr.ENGINES, 'own', lambda png, size: calls.append((png, threading.get_ident())) or [])
    reads = ocr.run_ocr_pages('own', [(b'0', (1, 1)), (b'1', (1, 1)), (b'2', (1, 1))])
    assert calls == []
    for read in reads:
        read()
    assert calls == [(b'0', threading.get_ident()), (b'1', threading.get_ident()), (b'2', threading.get_ident())]


def _settings(**env):
    clean = {k: v for k, v in os.environ.items() if k not in own.THREAD_ENV}
    done = subprocess.run(
        [sys.executable, '-B', '-c', 'from engine_v2.pipeline.ocr import own; '
         'print(own.AUTO_THREADS, own.single_intra_threads(), own.INTRA_OP_THREADS, own.MAX_PAGE_WORKERS)'],
        cwd=REPO, env={**clean, **env}, capture_output=True, text=True, timeout=60, check=True)
    return done.stdout.split()


def test_environment_turns_auto_off_and_fixes_the_values():
    cores = os.cpu_count() or 1
    assert _settings() == ['True', str(min(4, cores)), '2', '4']
    assert _settings(OWN_OCR_INTRA_THREADS='', OWN_OCR_PAGE_WORKERS=' ') == ['True', str(min(4, cores)), '2', '4']
    assert _settings(OWN_OCR_INTRA_THREADS='4', OWN_OCR_PAGE_WORKERS='2') == ['False', '4', '4', '2']
    assert _settings(OWN_OCR_PAGE_WORKERS='1') == ['False', '2', '2', '1']
    assert _settings(OWN_OCR_INTRA_THREADS='3') == ['False', '3', '3', '4']


def test_preload_loads_the_single_and_every_page_session(monkeypatch, loads):
    from demo.backend.ocr import localocr
    loaded, _ = loads
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    assert localocr.preload_own() == 'LOADED'
    assert sorted(loaded) == [2, 2, 2, 2, 4, 4]  # + the two-page slot 1 (slot 0 is the single session)
    _read(1)
    _read(4)
    assert sorted(loaded) == [2, 2, 2, 2, 4, 4]  # nothing is loaded on a later request


def test_doc_timing_records_auto_and_the_values_used(monkeypatch, tmp_path, capsys):
    import json
    from engine_v2.tests.test_doc_timing import image_pdf, text_pdf
    from engine_v2.tools import doc_timing as tool
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 8)
    monkeypatch.setitem(ocr.ENGINES, 'own', lambda png, size: [])
    monkeypatch.setattr(tool, 'own_available', lambda: True)
    root = tmp_path / 'FAKE-input'
    root.mkdir()
    image_pdf(root / 'one.pdf', text_pdf(tmp_path / 'source.pdf'))
    out = tmp_path / 'out'
    assert tool.main(['--root', str(root), '--out', str(out), '--warmup', '0']) == 0
    meta = json.loads((out / 'run.json').read_text())
    summary = (out / 'summary_brief.txt').read_text().splitlines()
    assert meta['options']['ocr_thread_mode'] == dict(mode='auto', single_intra=4, page_intra=2, page_workers_cap=4)
    assert 'OCR_THREADS own 2 4 4' in summary and 'OCR_THREADS_MODE auto 4 2 4' in summary
    assert 'OCR_THREADS_USED 4 1 1' in summary and meta['ocr_threads_used'] == [[4, 1, 1]]
    capsys.readouterr()


# ---------------------------------------------------------------- 11-19 T4b: two pages read with intra 4 x 2


def test_two_pages_use_two_intra_4_page_sessions_concurrently(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    _read(2)
    # slot 0 is the single intra-4 session (det-0), slot 1 one more intra-4 page session (det-1)
    assert loaded == [4, 4]
    # (a pool thread that is already idle may take the second page too: subset, as for 3 pages)
    assert len(used) == 2 and {det for det, _ in used} <= {'det-0-i4', 'det-1-i4'}
    assert threading.get_ident() not in {thread for _, thread in used}
    assert own.page_sessions(0, 4) is own.sessions()
    _read(3)
    assert loaded == [4, 4, 2, 2, 2]  # 3+ pages keep intra-2 page sessions, never the intra-4 ones
    assert {det for det, _ in used[2:]} <= {'det-2-i2', 'det-3-i2', 'det-4-i2'}
    _read(1)
    _read(2)
    assert loaded == [4, 4, 2, 2, 2]  # one page and two pages reuse what is loaded
    assert [det for det, _ in used[5:6]] == ['det-0-i4']  # the one-page read is on the single session
    assert own.page_workers(2) * own.page_intra_threads(2) <= 8


@pytest.mark.parametrize('cores, intra, workers', [(1, 2, 1), (2, 2, 1), (4, 2, 2), (6, 2, 2), (8, 4, 2), (16, 4, 2)])
def test_two_page_threads_stay_within_the_cores(monkeypatch, cores, intra, workers):
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: cores)
    assert own.page_intra_threads(2) == intra and own.page_workers(2) == workers
    assert workers == 1 or workers * intra <= cores
    # one page and 3+ pages are unchanged
    assert own.page_intra_threads(1) == own.page_intra_threads(3) == own.page_intra_threads(9) == own.INTRA_OP_THREADS


@pytest.mark.parametrize('intra, max_workers', [(2, 4), (4, 2), (3, 4), (2, 1)])
def test_fixed_values_keep_two_pages_as_before(monkeypatch, loads, intra, max_workers):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', False)
    monkeypatch.setattr(own, 'INTRA_OP_THREADS', intra)
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', max_workers)
    assert own.page_intra_threads(2) == intra
    assert own.page_workers(2) == max(1, min(2, max_workers, 8 // intra))
    _read(2)
    workers = own.page_workers(2)
    # slot 0 shares sessions(); a second worker loads one more session with the fixed threads
    assert loaded == [intra] * (2 if workers == 2 else 1)


def test_auto_with_one_page_worker_reads_two_pages_sequentially(monkeypatch, loads):
    loaded, used = loads
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', 1)
    assert own.page_intra_threads(2) == own.INTRA_OP_THREADS and own.page_workers(2) == 1
    _read(2)
    assert loaded == [4] and {thread for _, thread in used} == {threading.get_ident()}


def test_preload_also_loads_the_two_page_sessions(monkeypatch, loads):
    from demo.backend.ocr import localocr
    loaded, _ = loads
    monkeypatch.setenv('ENGINE_V2_OCR', 'own')
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    assert localocr.preload_own() == 'LOADED'
    assert sorted(loaded) == [2, 2, 2, 2, 4, 4]  # single (= two-page slot 0) + four intra-2 + two-page slot 1
    for pages in (1, 2, 3, 4, 7):
        _read(pages)
    assert sorted(loaded) == [2, 2, 2, 2, 4, 4]  # nothing is loaded on a later request


def test_doc_timing_records_two_pages_as_intra_4_x_2(monkeypatch, tmp_path, capsys, loads):
    import json
    import pymupdf
    from engine_v2.tests.test_doc_timing import _image_page, text_pdf
    from engine_v2.tools import doc_timing as tool
    monkeypatch.setattr(own, 'AUTO_THREADS', True)
    # The real own reader stays in ENGINES["own"] (pages run concurrently); recognize is model-free.
    monkeypatch.setattr(own, 'recognize', lambda png, size: [])
    monkeypatch.setattr(tool, 'own_available', lambda: True)
    root = tmp_path / 'FAKE-input'
    root.mkdir()
    source = text_pdf(tmp_path / 'source.pdf')
    for name, pages in (('one.pdf', 1), ('two.pdf', 2), ('three.pdf', 3)):
        with pymupdf.open(source) as original, pymupdf.open() as document:
            for _ in range(pages):
                _image_page(document, original[0])
            document.save(root / name)
    out = tmp_path / 'out'
    assert tool.main(['--root', str(root), '--out', str(out), '--warmup', '0']) == 0
    meta = json.loads((out / 'run.json').read_text())
    summary = (out / 'summary_brief.txt').read_text().splitlines()
    assert meta['ocr_threads_used'] == [[2, 3, 1], [4, 1, 1], [4, 2, 1]]
    assert 'OCR_THREADS_USED 4 2 1' in summary and 'OCR_THREADS_USED 4 1 1' in summary
    assert 'OCR_THREADS_USED 2 3 1' in summary
    assert 'OCR_THREADS_MODE auto 4 2 4' in summary  # mode line unchanged
    capsys.readouterr()
