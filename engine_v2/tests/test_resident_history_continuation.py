"""Synthetic-only continuation table recovery and omission safeguards."""
from datetime import date

import pytest

from engine_v2.engine import evaluate_document, load_rulepack
from engine_v2.extractors import resident_abstract as ra
from engine_v2.schemas.models import Verdict
from engine_v2.tests.test_engine import app
from engine_v2.tests.test_resident_abstract import header, table_head, row, page, wd

TODAY = date(2026, 11, 10)


def synthetic_pages(mode="normal"):
    applicant = "신청인: 김전북 (1999-01-01)"
    first = header(1, 2, applicant=applicant) + table_head(31.8)
    for i in range(8):
        first += row(34.4 + i * 4.3, i + 1, "전북특별자치도 가상시 합성로", f"{2010+i}-01-01")
    first += [wd(40, 73, "이하 여백", 1, 15)]
    head = table_head(21.1)
    if mode in {"split", "partial", "split_date"}:
        for word in head:
            if "발생일" in word.text or "세대주" in word.text:
                x0, y0, x1, y1 = word.bbox_px
                word.bbox_px = (x0, y0 + 1.2 / 100 * 2923, x1, y1 + 1.2 / 100 * 2923)
    if mode == "ambiguous":
        head = [word for word in head if "발생일" not in word.text and "세대주" not in word.text]
    tail = row(25.7, 9, "서울특별시 가상구 합성로", "2022-01-01")
    tail += row(30.1, 10, "전북특별자치도 가상시 시험로", "2023-01-01")
    if mode == "partial":
        next(word for word in tail if word.text == "2023-01-01").text = "2O23-O1-O1"
    if mode == "split_date":
        target = next(word for word in tail if word.text == "2023-01-01")
        tail.remove(target)
        tail += [wd(66, 30.1, "2023-", 1, 3), wd(69.2, 30.1, "01-01", 1, 3)]
    second = header(2, 2, applicant=applicant) + head + tail + [wd(40, 40, "이하 여백", 1, 15)]
    if mode == "attachment":
        second = header(2, 2, applicant=applicant) + [
            wd(25, 30, "추가 안내 자료", 1, 20), wd(70, 35, "번호", 1, 4),
            wd(20, 37, "신고일 안내", 1, 12), wd(20, 42, "2022-01-01", 1, 9),
            wd(20, 48, "2023-01-01", 1, 9), wd(80, 42, "9", 1, 2), wd(80, 48, "10", 1, 2)]
    return [page(0, first), page(1, second)]



def evaluate(pages, **kwargs):
    application = app(**kwargs)
    return evaluate_document(application.documents[0], pages, application,
                             load_rulepack("doubling_savings"), today=TODAY)


@pytest.mark.parametrize("mode", ["normal", "split"])
@pytest.mark.parametrize("scale", [.65, 1, 1.7])
def test_eight_plus_two_rows_are_complete(mode, scale):
    pages = synthetic_pages(mode)
    for image, result in pages:
        image.pixel_size = tuple(round(size * scale) for size in image.pixel_size)
        for word in result.words:
            word.bbox_px = tuple(value * scale for value in word.bbox_px)
    result = ra.extract(pages, today=TODAY)
    assert [entry.no for entry in result.history] == list(range(1, 11))
    assert [entry.page for entry in result.history] == [0] * 8 + [1] * 2
    assert result.fields["address_history_count"].value == 10
    assert not result.history_table_issues
    assert all(v.passed for v in result.validations)
    assert evaluate(pages).verdict == Verdict.SUITABLE


def test_one_page_unchanged():
    pages = synthetic_pages()[:1]
    next(word for word in pages[0][1].words if word.text == "1/2").text = "1/1"
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8 and not result.history_table_issues
    assert evaluate(pages).verdict == Verdict.SUITABLE


def test_single_continuation_row_requires_a_proven_previous_table():
    from engine_v2.pipeline.layout import group_lines, normalize

    pages = synthetic_pages("split")
    words = pages[1][1].words
    words[:] = [word for word in words if word.bbox_px[1] / 2923 * 100 < 29]
    image, result = pages[1]
    lines = group_lines(normalize(result.words, image.page, image.pixel_size))
    assert ra._table_bounds(lines) is None
    extracted = ra.extract(pages, today=TODAY)
    assert len(extracted.history) == 9 and not extracted.history_table_issues


@pytest.mark.parametrize("mode", ["ambiguous", "partial", "split_date"])
def test_unread_continuation_is_reviewed_without_mutating_prior_history(mode):
    baseline = ra.extract(synthetic_pages(), today=TODAY)
    pages = synthetic_pages(mode)
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8
    assert result.history_table_issues
    assert [entry.address_text for entry in result.history] == [entry.address_text for entry in baseline.history[:8]]
    assert result.fields["address_history"].confidence <= .4
    assert result.fields["issue_date"].confidence >= .9
    assert result.fields["name"].confidence >= .9
    assert any(not v.passed and v.name == "history_tables_readable" for v in result.validations)
    assert evaluate(pages).verdict == Verdict.NEEDS_REVIEW


@pytest.mark.parametrize("mode", ["ambiguous", "partial", "split_date"])
@pytest.mark.parametrize("defect", ["date", "identity"])
def test_independent_confirmed_failure_survives_new_history_uncertainty(mode, defect):
    kwargs = {"issue": "2026-11-09"} if defect == "date" else {"name": "가상다른인"}
    assert evaluate(synthetic_pages(), **kwargs).verdict == Verdict.UNSUITABLE
    assert evaluate(synthetic_pages(mode), **kwargs).verdict == Verdict.UNSUITABLE


def test_non_history_attachment_does_not_become_a_table():
    result = ra.extract(synthetic_pages("attachment"), today=TODAY)
    assert len(result.history) == 8
    assert not result.history_table_issues


def test_one_unrecovered_row_with_partial_ordered_header_requires_review():
    pages = synthetic_pages("split")
    words = pages[1][1].words
    words[:] = [word for word in words if word.text not in {"주", "소"}
                and word.bbox_px[1] / 2923 * 100 < 29]
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8 and result.history_table_issues == ["TABLE_NOT_FOUND"]
    assert evaluate(pages).verdict == Verdict.NEEDS_REVIEW


def test_detected_table_without_rows_cannot_pass_the_direct_engine():
    pages = synthetic_pages()
    pages[1][1].words[:] = [word for word in pages[1][1].words if word.bbox_px[1] / 2923 * 100 < 25]
    result = ra.extract(pages, today=TODAY)
    assert result.history_empty_page and not result.history_table_issues
    assert result.fields["issue_date"].confidence >= .9
    assert evaluate(pages).verdict == Verdict.NEEDS_REVIEW
    assert evaluate(pages, issue="2026-11-09").verdict == Verdict.UNSUITABLE


@pytest.mark.parametrize("change", ["distant", "reordered", "label_misread", "ordinal_misread"])
def test_unsupported_headers_and_ordinals_never_create_rows(change):
    pages = synthetic_pages("split")
    words = pages[1][1].words
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        if change == "distant" and ("발생일" in word.text or "세대주" in word.text):
            word.bbox_px = (x0, y0 + 6 / 100 * 2923, x1, y1 + 6 / 100 * 2923)
        elif change == "reordered" and word.text == "번호":
            word.bbox_px = (80 / 100 * 2066, y0, 84 / 100 * 2066, y1)
        elif change == "label_misread" and "발생일" in word.text:
            word.text = "발섕일 / 신고1"
        elif change == "label_misread" and "세대주" in word.text:
            word.text = "세대쥬"
        elif change == "ordinal_misread" and word.text in {"9", "10"}:
            word.text = "O" + word.text
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8
    assert evaluate(pages).verdict != Verdict.SUITABLE


def test_split_report_header_label_is_supported_without_changing_date_values():
    pages = synthetic_pages("split")
    words = pages[1][1].words
    words[:] = [word for word in words if "발생일" not in word.text and "세대주" not in word.text]
    words += [wd(65, 21.9, "신고", 1, 4), wd(65, 23, "일", 1, 2)]
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 10 and not result.history_table_issues


def test_partial_legacy_table_with_unassigned_date_evidence_requires_review():
    pages = synthetic_pages()
    words = pages[1][1].words
    words[:] = [word for word in words if word.text != "10"]
    next(word for word in words if word.text == "2023-01-01").text = "2O23-O1-O1"
    result = ra.extract(pages, today=TODAY)
    assert result.history_table_issues
    assert result.fields["issue_date"].confidence >= .9
    assert evaluate(pages).verdict == Verdict.NEEDS_REVIEW


@pytest.mark.parametrize("text", ["2O23년O1월O1일", "미상2023", "2023X01X01", "OOOO-OO-OO"])
def test_damaged_date_and_ordinal_cannot_hide_an_extra_row(text):
    pages = synthetic_pages("split")
    words = pages[1][1].words
    words[:] = [word for word in words if word.text != "10"]
    next(word for word in words if word.text == "2023-01-01").text = text
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8 and result.history_table_issues
    assert evaluate(pages).verdict == Verdict.NEEDS_REVIEW


@pytest.mark.parametrize("gap,recover", [(1.49, True), (1.51, False), (3.51, False)])
def test_header_line_distance_boundary(gap, recover):
    pages = synthetic_pages("split")
    for word in pages[1][1].words:
        if "발생일" in word.text or "세대주" in word.text:
            x0, y0, x1, y1 = word.bbox_px
            delta = (gap - 1.2) / 100 * 2923
            word.bbox_px = (x0, y0 + delta, x1, y1 + delta)
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == (10 if recover else 8)
    assert bool(result.history_table_issues) is not recover


def test_dates_and_words_without_address_geometry_are_not_history():
    pages = synthetic_pages("attachment")
    pages[1][1].words += [wd(8, 30, "번호", 1, 4), wd(80, 33, "세대주", 1, 8)]
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8
    assert not result.history_table_issues


@pytest.mark.parametrize("marker", ["병역", "이하 여백"])
@pytest.mark.parametrize("has_header", [False, True])
def test_other_sections_after_table_end_are_never_history(marker, has_header):
    pages = synthetic_pages("split" if has_header else "attachment")
    words = header(2, 2, applicant="신청인: 김전북 (1999-01-01)") + [wd(8, 20, marker, 1, 8)]
    words += [word for word in pages[1][1].words if word.bbox_px[1] / 2923 * 100 >= 21]
    if not has_header:
        words += row(40, 9, "서울특별시 가상구 합성로", "2022-01-01")
        words += row(45, 10, "전북특별자치도 가상시 시험로", "2023-01-01")
    pages[1][1].words = words
    result = ra.extract(pages, today=TODAY)
    assert len(result.history) == 8 and not result.history_table_issues
