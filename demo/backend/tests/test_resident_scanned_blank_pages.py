"""L1 (11-18 보완): a scanned blank sheet after an abstract is still a blank page (synthetic only).

Scan specks, the page frame, a printed page number and a repeated address-table header are not content.
"""
import json

import pytest

from engine_v2.tests.test_resident_abstract import row, table_head, wd

from .run_p18_applicant_precheck_scenarios import resident_words
from .test_resident_blank_pages import _header_only, _read, _two_pages


def _noise():
    return [wd(20 + 7 * i, 30 + 6 * i, text, .3, 1) for i, text in enumerate([".", "'", ",", "·", "`", "-"])]


def _frame():
    return ([wd(2.0, y, "|", .4, .5) for y in range(28, 77, 6)]
            + [wd(97.0, y, "l", .4, .5) for y in range(28, 77, 6)])


@pytest.mark.parametrize("extra", ["noise", "frame", "page_number", "table_head", "table_head_noise"])
def test_scanned_blank_third_page_is_not_a_duplicate(tmp_path, extra):
    page = _header_only("2/2") + {
        "noise": _noise(), "frame": _frame(), "page_number": [wd(48.0, 76.0, "- 3 -", .9, 4)],
        "table_head": table_head(21.1), "table_head_noise": table_head(21.1) + _noise(),
    }[extra]
    ocr, result = _read(tmp_path, _two_pages() + [page])
    data = json.loads(ocr.fields["쪽표기자료"])
    assert data["markers"] == [[1, 2], [2, 2]] and data["blank_pages"] == 1
    assert result.status == "PASS" and "PAGES_DUPLICATED" not in result.codes


def test_duplicated_page_with_a_history_row_still_fails(tmp_path):
    page = _header_only("2/2") + table_head(21.1) + row(24.0, 3, "전북특별자치도 전주시 가상동", "2024-01-01")
    _, result = _read(tmp_path, _two_pages() + [page])
    assert result.status == "FAIL" and "PAGES_DUPLICATED" in result.codes


def test_table_only_page_without_a_marker_stays_unreadable(tmp_path):
    page = _header_only("읽기불가") + table_head(21.1)
    ocr, result = _read(tmp_path, _two_pages() + [page])
    assert "blank_pages" not in json.loads(ocr.fields["쪽표기자료"])
    assert result.status == "NEEDS_REVIEW" and "PAGES_UNREADABLE" in result.codes


def test_table_only_page_cannot_supply_a_missing_page_number(tmp_path):
    pages = [resident_words("1/3"), resident_words("2/3", index=1), _header_only("2/3") + table_head(21.1) + _noise()]
    _, result = _read(tmp_path, pages)
    assert result.status == "FAIL" and "PAGES_INCOMPLETE" in result.codes
