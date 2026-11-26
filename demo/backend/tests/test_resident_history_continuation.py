"""Synthetic upload-path checks for continuation history, with fake local OCR."""
from dataclasses import replace
from datetime import date

import pytest

from engine_v2.tests.test_resident_history_continuation import synthetic_pages
from demo.backend.rules.doc_check import check_document
from demo.backend.tests.run_p8_localocr_scenarios import abstract_slot
from demo.backend.tests.run_p18_applicant_precheck_scenarios import IDENTITY
from demo.backend.tests.test_resident_blank_pages import _read
from .scan_guard import scan_guard_off  # noqa: F401 (fixture)

# Subject: other resident logic; the 11-26 scan guard is tested in test_resident_scan_guard.py.
pytestmark = pytest.mark.usefixtures("scan_guard_off")


def words(mode):
    return [result.words for _, result in synthetic_pages(mode)]


@pytest.mark.parametrize("mode", ["normal", "split"])
def test_complete_eight_plus_two_keeps_pass(tmp_path, mode):
    ocr, result = _read(tmp_path, words(mode))
    assert result.status == "PASS"
    assert ocr.fields["주소이력건수"] == "10"
    assert ocr.fields["전입일"] == "2023-01-01"
    assert "주소이력상태" not in ocr.fields


@pytest.mark.parametrize("mode", ["ambiguous", "partial", "split_date"])
def test_unread_continuation_prevents_pass_without_guessing(tmp_path, mode):
    ocr, result = _read(tmp_path, words(mode))
    assert result.status == "NEEDS_REVIEW"
    assert "ADDRESS_HISTORY_INCOMPLETE" in result.codes
    assert "TABLE_NOT_FOUND" in ocr.fields["주소이력불확실사유"]
    assert ocr.fields["전입일"] == "불확실"
    assert ocr.fields["주소이력건수"] == "불확실"
    assert ocr.fields["현주소시도"] == "불확실"
    assert "전입일" not in ocr.bboxes
    assert ocr.confidence >= .85


def test_unrelated_attachment_adds_no_history_review(tmp_path):
    ocr, result = _read(tmp_path, words("attachment"))
    assert result.status == "PASS"
    assert ocr.fields["주소이력건수"] == "8"
    assert "ADDRESS_HISTORY_INCOMPLETE" not in result.codes


def test_partial_header_with_one_supported_row_cannot_pass(tmp_path):
    data = words("split")
    data[1] = [word for word in data[1] if word.text not in {"주", "소"}
               and word.bbox_px[1] / 2923 * 100 < 29]
    ocr, result = _read(tmp_path, data)
    assert result.status == "NEEDS_REVIEW"
    assert "TABLE_NOT_FOUND" in ocr.fields["주소이력불확실사유"]


@pytest.mark.parametrize("text", ["2O23년O1월O1일", "미상2023", "2023X01X01", "OOOO-OO-OO"])
def test_damaged_date_and_ordinal_never_reaches_pass(tmp_path, text):
    data = words("split")
    data[1] = [word for word in data[1] if word.text != "10"]
    next(word for word in data[1] if word.text == "2023-01-01").text = text
    ocr, result = _read(tmp_path, data)
    assert result.status == "NEEDS_REVIEW"
    assert ocr.fields["주소이력건수"] == "불확실"


@pytest.mark.parametrize("mode", ["ambiguous", "partial", "split_date"])
@pytest.mark.parametrize("defect", ["declared_date", "identity", "missing_page"])
def test_new_uncertainty_preserves_independent_confirmed_fail(tmp_path, mode, defect):
    data = words(mode)
    if defect == "missing_page":
        for page in data:
            for word in page:
                if word.text in {"1/2", "2/2"}:
                    word.text = word.text.replace("/2", "/3")
    ocr, _ = _read(tmp_path, data)
    identity = replace(IDENTITY, name="가상다른인") if defect == "identity" else IDENTITY
    declared = date(2026, 11, 9) if defect == "declared_date" else None
    result = check_document(abstract_slot(), ocr, identity=identity, declared_issue_date=declared)
    assert result.status == "FAIL"
    assert "ADDRESS_HISTORY_INCOMPLETE" in result.codes
    expected = {"declared_date": "DECLARED_DATE_MISMATCH", "identity": "IDENTITY_MISMATCH",
                "missing_page": "PAGES_INCOMPLETE"}[defect]
    assert any(f.code == expected and f.severity == "FAIL" for f in result.findings)


def test_one_page_and_single_entry_policy_are_preserved(tmp_path):
    data = words("normal")[:1]
    next(word for word in data[0] if word.text == "1/2").text = "1/1"
    ocr, result = _read(tmp_path, data)
    assert result.status == "PASS" and ocr.fields["주소이력건수"] == "8"
    # A one-entry history retains the pre-existing omission-suspicion review policy.
    # Keep the page's 이하 여백 (11-26 end evidence): this checks the single-entry policy, not a cut page.
    data[0] = [word for word in data[0] if word.bbox_px[1] / 2923 * 100 < 38 or word.text == "이하 여백"]
    ocr, result = _read(tmp_path, data)
    assert ocr.fields["주소이력건수"] == "1"
    assert result.status == "NEEDS_REVIEW"
    assert "PAST_ADDRESS_OMISSION_SUSPECTED" in result.codes


def test_existing_number_and_page_defects_stay_non_pass(tmp_path):
    for defect in ("duplicate", "number_gap", "unreadable_number"):
        data = words("normal")
        if defect == "duplicate":
            next(word for word in data[1] if word.text == "2/2").text = "1/2"
        else:
            target = next(word for word in data[1] if word.text == "10")
            target.text = "11" if defect == "number_gap" else "O10"
        _, result = _read(tmp_path, data)
        assert result.status != "PASS"
        if defect == "duplicate":
            assert result.status == "FAIL" and "PAGES_INCOMPLETE" in result.codes


def test_new_history_signal_does_not_disable_existing_page_confidence_exception(tmp_path):
    from copy import deepcopy
    first, _ = words("normal")
    _, unread = words("ambiguous")
    for word in first:
        if word.text == "1/2":
            word.text = "1/3"
    for word in unread:
        if word.text == "2/2":
            word.text = "2/3"
    ocr, result = _read(tmp_path, [first, deepcopy(first), unread])
    assert ocr.confidence == .4
    assert "TABLE_NOT_FOUND" in ocr.fields["주소이력불확실사유"]
    assert result.status == "FAIL" and "PAGES_INCOMPLETE" in result.codes


@pytest.mark.parametrize("marker", ["병역", "이하 여백"])
@pytest.mark.parametrize("has_header", [False, True])
def test_non_history_section_after_end_adds_no_review(tmp_path, marker, has_header):
    from engine_v2.tests.test_resident_abstract import header, row, wd

    data = words("split" if has_header else "attachment")
    second = header(2, 2, applicant="신청인: 김전북 (1999-01-01)") + [wd(8, 20, marker, 1, 8)]
    second += [word for word in data[1] if word.bbox_px[1] / 2923 * 100 >= 21]
    if not has_header:
        second += row(40, 9, "서울특별시 가상구 합성로", "2022-01-01")
        second += row(45, 10, "전북특별자치도 가상시 시험로", "2023-01-01")
    data[1] = second
    ocr, result = _read(tmp_path, data)
    assert result.status == "PASS"
    assert ocr.fields["주소이력건수"] == "8"
    assert "ADDRESS_HISTORY_INCOMPLETE" not in result.codes
