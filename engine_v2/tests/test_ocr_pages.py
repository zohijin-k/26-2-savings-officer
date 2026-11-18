"""run_ocr_pages: page order, concurrent own pages, unchanged sequential behaviour (model-free)."""
import threading

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
    monkeypatch.setitem(ocr.ENGINES, 'own', recognize)
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
