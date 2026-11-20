"""run_ocr_pages: page order, concurrent own pages, unchanged sequential behaviour (model-free)."""
import threading

import pytest

from engine_v2.pipeline import ocr
from engine_v2.pipeline.ocr import OcrWord, own


def _images(n):
    return [(f'page-{i}'.encode(), (10, 10)) for i in range(n)]


def test_concurrent_own_pages_keep_page_order(monkeypatch):
    threads = set()
    barrier = threading.Barrier(3, timeout=5)

    def recognize(png, size):
        threads.add((threading.get_ident(), own._worker.slot))
        barrier.wait()  # all three pages are read at the same time
        return [OcrWord(png.decode(), .9, (0, 0, 1, 1))]
    # The real own reader (ENGINES["own"] untouched) calls own.recognize per page.
    monkeypatch.setattr(own, 'recognize', recognize)
    monkeypatch.setattr(own, 'prepare_page_workers', lambda pages: 3)
    results = [read() for read in ocr.run_ocr_pages('own', _images(3))]
    assert [r.words[0].text for r in results] == ['page-0', 'page-1', 'page-2']
    assert len(threads) == 3 and {slot for _, slot in threads} == {0, 1, 2}


def test_single_page_and_other_engines_stay_sequential(monkeypatch):
    monkeypatch.setattr(own, 'prepare_page_workers', lambda pages: (_ for _ in ()).throw(AssertionError))
    calls = []
    monkeypatch.setitem(ocr.ENGINES, 'own', lambda png, size: calls.append(threading.get_ident()) or [])
    monkeypatch.setitem(ocr.ENGINES, 'easyocr', lambda png, size: calls.append(threading.get_ident()) or [])
    [read() for read in ocr.run_ocr_pages('own', _images(1))]
    [read() for read in ocr.run_ocr_pages('easyocr', _images(3))]
    assert calls == [threading.get_ident()] * 4


def test_wrapped_reader_is_called_lazily_in_order():
    calls = []

    def run(engine, png, size):
        calls.append(png)
        if png == b'page-1':
            raise ValueError('page error')
        return ocr.OcrResult(engine)
    reads = ocr.run_ocr_pages('own', _images(3), run=run)
    assert calls == []
    next(reads)()
    assert calls == [b'page-0']
    try:
        next(reads)()
    except ValueError:
        pass
    next(reads)()  # a page error does not end the remaining pages
    assert calls == [b'page-0', b'page-1', b'page-2']


def test_worker_budget_stays_within_logical_cores(monkeypatch):
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 12)
    assert own.page_workers(1) == 1 and own.page_workers(3) == 3 and own.page_workers(9) == own.MAX_PAGE_WORKERS
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 4)
    assert own.page_workers(4) * own.INTRA_OP_THREADS <= 4
    monkeypatch.setattr(own.os, 'cpu_count', lambda: None)
    assert own.page_workers(4) == 1


# ---------------------------------------------------------------- only the real own reader runs pages concurrently


@pytest.mark.parametrize('max_workers', [1, 4, 8])
def test_swapped_reader_reads_pages_in_order_whatever_the_worker_limit(monkeypatch, max_workers):
    """A reader swapped into ENGINES["own"] (e.g. a fake that hands out page results in call order)
    is called sequentially, lazily and on the caller's thread, whatever MAX_PAGE_WORKERS says."""
    monkeypatch.setattr(own, 'MAX_PAGE_WORKERS', max_workers)
    monkeypatch.setattr(own.os, 'cpu_count', lambda: 16)
    monkeypatch.setattr(own, 'prepare_page_workers', lambda pages: (_ for _ in ()).throw(AssertionError(pages)))
    pages = iter(_images(4))
    calls = []

    def recognize(png, size):
        expected, _ = next(pages)
        calls.append((png, threading.current_thread().name))
        return [OcrWord(expected.decode(), .9, (0, 0, 1, 1))]
    monkeypatch.setitem(ocr.ENGINES, 'own', recognize)
    reads = ocr.run_ocr_pages('own', _images(4))
    texts = []
    for index, read in enumerate(reads):
        assert len(calls) == index  # nothing is read ahead of the caller
        texts.append(read().words[0].text)
    assert texts == [f'page-{i}' for i in range(4)]
    assert [png for png, _ in calls] == [f'page-{i}'.encode() for i in range(4)]
    assert {name for _, name in calls} == {threading.current_thread().name}


def _concurrent_reader_threads(monkeypatch):
    names = set()
    barrier = threading.Barrier(4, timeout=5)

    def recognize(png, size):
        names.add(threading.current_thread().name)
        barrier.wait()  # passes only when all four pages are read at the same time
        return [OcrWord(png.decode(), .9, (0, 0, 1, 1))]
    monkeypatch.setattr(own, 'recognize', recognize)
    monkeypatch.setattr(own, 'prepare_page_workers', lambda pages: 4)
    texts = [read().words[0].text for read in ocr.run_ocr_pages('own', _images(4))]
    assert texts == [f'page-{i}' for i in range(4)]
    return names


def test_real_reader_reads_pages_concurrently(monkeypatch):
    names = _concurrent_reader_threads(monkeypatch)
    assert len(names) == 4 and all(name.startswith('own-page') for name in names)


def test_measurement_wrapper_around_the_real_reader_keeps_concurrency(monkeypatch):
    """doc_timing wraps ENGINES["own"] and sets __wrapped__; that still counts as the real reader."""
    original = ocr.ENGINES['own']

    def timed(png, size):
        return original(png, size)
    timed.__wrapped__ = original
    monkeypatch.setitem(ocr.ENGINES, 'own', timed)
    names = _concurrent_reader_threads(monkeypatch)
    assert len(names) == 4 and all(name.startswith('own-page') for name in names)
