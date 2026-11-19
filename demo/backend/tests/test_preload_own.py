"""Server start preloads own models; failure falls back to first-call loading (model-free)."""
from functools import lru_cache

from demo.backend.ocr import localocr
from engine_v2.pipeline.ocr import own


def test_other_engines_are_not_loaded(monkeypatch):
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    monkeypatch.setattr(own, "sessions", lambda: (_ for _ in ()).throw(AssertionError))
    assert localocr.preload_own() == "SKIPPED"


def test_failure_does_not_block_start_and_first_call_loads_again(monkeypatch):
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    attempts = []

    @lru_cache(maxsize=1)
    def sessions():
        attempts.append(1)
        if len(attempts) == 1:
            raise FileNotFoundError("model missing")
        return "det", "rec", []
    monkeypatch.setattr(own, "sessions", sessions)
    assert localocr.preload_own() == "FAILED"
    assert sessions() == ("det", "rec", [])  # the cache did not keep the failure
    assert len(attempts) == 2


def test_success_loads_every_page_worker_and_warms_the_reader(monkeypatch):
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    calls = []
    monkeypatch.setattr(own, "sessions", lambda: calls.append("sessions"))
    monkeypatch.setattr(own, "prepare_page_workers", lambda n: calls.append(("workers", n)) or n)
    monkeypatch.setattr(own, "recognize", lambda png, size: calls.append(("recognize", size)) or [])
    assert localocr.preload_own() == "LOADED"
    assert calls == ["sessions", ("workers", own.MAX_PAGE_WORKERS), ("workers", 2), ("recognize", (32, 32))]
