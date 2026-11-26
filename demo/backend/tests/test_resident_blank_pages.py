"""L1: content-less pages after a resident abstract are excluded from page counting only.

Synthetic only: image-only PDFs with a fake OCR engine returning authored words per page.
"""
import json
import os
from unittest.mock import patch

import pytest

from ..ocr.localocr import ENGINE_ENV, LocalOcr
from ..rules.doc_check import check_document
from .run_p8_localocr_scenarios import abstract_slot, make_image_pdf
from .run_p18_applicant_precheck_scenarios import IDENTITY, resident_words
from .scan_guard import scan_guard_off  # noqa: F401 (fixture)

# Subject: other resident logic; the 11-26 scan guard is tested in test_resident_scan_guard.py.
pytestmark = pytest.mark.usefixtures("scan_guard_off")


def _read(tmp_path, pages):
    from engine_v2.pipeline import ocr as v2ocr

    path = make_image_pdf(tmp_path / "synthetic-abstract.pdf", pages=len(pages))
    pending = iter(pages)
    with patch.dict(os.environ, {ENGINE_ENV: "l1-synthetic"}), \
            patch.dict(v2ocr.ENGINES, {"l1-synthetic": lambda png, size: next(pending)}):
        result = LocalOcr().read(str(path), None)
    assert result is not None
    return result, check_document(abstract_slot(), result, identity=IDENTITY)


def _header_only(marker):
    """The repeated page header box of a web-printed abstract, without any body rows."""
    from engine_v2.tests.test_resident_abstract import header

    words = header(1, 1, name=IDENTITY.name)
    for word in words:
        if word.text == "1/1":
            word.text = marker
    return words


def _two_pages():
    return [resident_words("1/2"), resident_words("2/2", index=1)]


def test_repeated_header_page_after_two_page_abstract_is_not_a_duplicate(tmp_path):
    ocr, result = _read(tmp_path, _two_pages() + [_header_only("2/2")])
    assert result.status == "PASS" and "PAGES_DUPLICATED" not in result.codes
    data = json.loads(ocr.fields["쪽표기자료"])
    assert data["markers"] == [[1, 2], [2, 2]] and data["blank_pages"] == 1 and ocr.page_count == 3


def test_blank_page_is_excluded_from_page_counting(tmp_path):
    ocr, result = _read(tmp_path, _two_pages() + [[]])
    data = json.loads(ocr.fields["쪽표기자료"])
    assert data["markers"] == [[1, 2], [2, 2]] and data["blank_pages"] == 1
    assert "PAGES_DUPLICATED" not in result.codes and "PAGES_INCOMPLETE" not in result.codes
    # The blank page still lowers header consistency; the document is never failed for it.
    assert result.status in ("PASS", "NEEDS_REVIEW")


@pytest.mark.parametrize("extra, code", [
    # A duplicated page with body rows is still a duplicate.
    ("duplicate_body", "PAGES_DUPLICATED"),
    # A content-less page cannot supply a missing page.
    ("missing_with_header_only", "PAGES_INCOMPLETE"),
])
def test_pages_with_content_and_missing_pages_keep_failing(tmp_path, extra, code):
    if extra == "duplicate_body":
        pages = _two_pages() + [resident_words("2/2", index=1)]
    else:
        pages = [resident_words("1/3"), resident_words("2/3", index=1), _header_only("2/3")]
    _, result = _read(tmp_path, pages)
    assert result.status == "FAIL" and code in result.codes


def test_content_less_page_with_its_own_marker_still_counts(tmp_path):
    # A header-only page carrying the only "2/2" marker is kept: it is that page, not an extra one.
    ocr, result = _read(tmp_path, [resident_words("1/2"), _header_only("2/2")])
    data = json.loads(ocr.fields["쪽표기자료"])
    assert data["markers"] == [[1, 2], [2, 2]] and "blank_pages" not in data
    assert "PAGES_INCOMPLETE" not in result.codes and "PAGES_DUPLICATED" not in result.codes


def test_invalid_blank_page_count_is_unreadable(tmp_path):
    ocr, _ = _read(tmp_path, _two_pages() + [_header_only("2/2")])
    data = json.loads(ocr.fields["쪽표기자료"])
    for bad in (-1, "1", 1.0):
        fields = dict(ocr.fields, 쪽표기자료=json.dumps(dict(data, blank_pages=bad)))
        from dataclasses import replace
        assert "PAGES_UNREADABLE" in check_document(abstract_slot(), replace(ocr, fields=fields),
                                                    identity=IDENTITY).codes
