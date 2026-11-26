"""11-26 Phase 1 scanned-abstract guard switch for tests whose subject is other resident logic.

`SCAN_ABSTRACT_REVIEW_GUARD` keeps every OCR-read 주민등록초본 out of automatic PASS. Tests about blank pages,
continuation tables, note numbering or viewing-copy marks assert "no other finding → PASS"; they opt in to
`scan_guard_off` to keep testing that logic in isolation. The guard itself (production default on) is tested in
test_resident_scan_guard.py: the same complete scan is NEEDS_REVIEW with exactly SCAN_UNVERIFIED.
"""
import pytest

from ..ocr import localocr


@pytest.fixture
def scan_guard_off(monkeypatch):
    monkeypatch.setattr(localocr, "SCAN_ABSTRACT_REVIEW_GUARD", False)
