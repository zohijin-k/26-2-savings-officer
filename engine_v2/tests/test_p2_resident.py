"""Separated law-note numbering and unresolved history confidence propagate."""
from datetime import date

import pytest

from engine_v2.engine import evaluate_document, load_rulepack
from engine_v2.extractors import resident_abstract as reader
from engine_v2.pipeline.ocr import OcrWord
from engine_v2.schemas.models import Verdict
from engine_v2.tests import p2_resident_samples as sample
from engine_v2.tests.test_engine import app


@pytest.mark.parametrize("name", ["가상", "가상인", "가상인명"])
@pytest.mark.parametrize("scale,jitter,skew", [(1, 0, 0), (.7, 1, 4), (1.8, 2, -5)])
@pytest.mark.parametrize("boundary", [False, True])
def test_unequal_font_note_numbers_preserve_multisheet_history(name, scale, jitter, skew, boundary):
    pages = sample.resident(name=name, scale=scale, jitter=jitter, skew=skew, boundary=boundary)
    result = reader.extract(pages)
    assert all(validation.passed for validation in result.validations), [v for v in result.validations if not v.passed]
    assert result.warnings == []
    assert result.fields["name"].value == name
    assert result.fields["birth_date"].value == date(1999, 1, 1)
    assert result.fields["issue_date"].value == date(2026, 3, 3)
    assert [entry.no for entry in result.history] == [1, 2, 3, 4, 5, 6, 7, 9, 11]
    assert result.history[-1].notes[0].startswith("[행정구역")
    assert result.history[-2].notes[0].startswith("[도로명")
    assert all(field.confidence >= .9 for key, field in result.fields.items() if key != "issuer")


@pytest.mark.parametrize("defect", ["first", "last", "all", "middle", "note", "duplicate", "unreadable"])
def test_unreadable_or_missing_number_stays_failed_and_caps_all_fields(defect):
    result = reader.extract(sample.damage(sample.resident(), defect))
    assert not next(v.passed for v in result.validations if v.name == "history_numbers_sequential")
    assert result.warnings
    assert all(field.confidence <= .4 for field in result.fields.values())
    assert result.fields["name"].value == sample.NAME
    assert result.fields["issue_date"].value == date(2026, 3, 3)


@pytest.mark.parametrize("offset", [4, 20])
def test_contiguous_numbering_start_remains_compatible(offset):
    result = reader.extract(sample.resident(offset=offset))
    assert all(validation.passed for validation in result.validations)
    assert result.warnings == []


def test_orphan_number_cannot_be_discarded_as_continuation():
    pages = sample.resident()
    pages[2][1].words.append(OcrWord("12", .99, (170, 1250, 221, 1296)))
    result = reader.extract(pages)
    assert not next(v.passed for v in result.validations if v.name == "history_numbers_sequential")


def test_ambiguous_note_numbers_do_not_complete_history():
    pages = sample.resident()
    pages[2][1].words.append(OcrWord("10", .99, (171, 1102, 222, 1148)))
    result = reader.extract(pages)
    assert not next(v.passed for v in result.validations if v.name == "history_numbers_sequential")


@pytest.mark.parametrize("wrong_issue,wrong_residence", [(True, False), (False, True), (True, True)])
def test_core_resident_evaluation_does_not_reject_untrusted_history(wrong_issue, wrong_residence):
    pages = sample.damage(sample.resident(), "middle")
    if wrong_residence:
        for page, result in pages:
            for word in result.words:
                word.text = word.text.replace("전라북도", "경기도").replace("전북특별자치도", "경기도")
    application = app(name=sample.NAME, birth=date(1999, 1, 1),
                      issue="2026-03-02" if wrong_issue else sample.ISSUE, announce=date(2026, 3, 1))
    result = evaluate_document(application.documents[0], pages, application, load_rulepack("doubling_savings"))
    assert result.verdict == Verdict.NEEDS_REVIEW
    assert result.review_reasons


def test_non_note_near_number_is_never_reclassified_as_a_note():
    pages = sample.resident()
    note = next(word for word in pages[2][1].words if word.text.startswith("[행정구역"))
    note.text = "전북특별자치도 가상시 가상로"
    result = reader.extract(pages)
    assert not next(v.passed for v in result.validations if v.name == "history_numbers_sequential")


@pytest.mark.parametrize("continuation", [False, True])
def test_unnumbered_bracketed_annotation_keeps_legacy_note_semantics(continuation):
    pages = sample.resident()
    y = 1158 if continuation else 1250
    pages[2][1].words.append(OcrWord("[가상 추가 안내]", .99, (278, y, 1054, y + 28)))
    result = reader.extract(pages)
    assert all(validation.passed for validation in result.validations)
    assert result.warnings == []


def _without_row(pages, number):
    """Drop every OCR word of one history row (its ordinal line ±1.3% of page height)."""
    for page, result in pages:
        height = page.pixel_size[1]
        found = [w for w in result.words if w.bbox_px[0] / page.pixel_size[0] * 100 < 11.5 and w.text == str(number)]
        if found:
            centre = (found[0].bbox_px[1] + found[0].bbox_px[3]) / 2
            result.words = [w for w in result.words
                            if abs((w.bbox_px[1] + w.bbox_px[3]) / 2 - centre) > .013 * height]
    return pages


def test_numbered_note_without_following_entry_is_an_incomplete_history():
    # 11-26: 마지막 건(11)을 못 읽으면 메모 10만 남아 순번 1~10이 이어져 보인다. 메모는 다음 건에 붙으므로
    # 뒤따르는 건 없는 순번 메모는 끝 이력 누락이다.
    result = reader.extract(_without_row(sample.resident(), 11))
    check = next(v for v in result.validations if v.name == "history_numbers_sequential")
    assert not check.passed and "뒤따르는 건 없는 메모 순번 [10]" in check.detail
    assert all(field.confidence <= .4 for field in result.fields.values())


def test_complete_history_with_inner_numbered_notes_still_passes():
    result = reader.extract(sample.resident())
    assert all(validation.passed for validation in result.validations)


def _drop_band(pages, index, low, high):
    """Remove the OCR words of one page whose centre lies between low% and high% of the page height."""
    page, result = pages[index]
    result.words = [w for w in result.words
                    if not low < (w.bbox_px[1] + w.bbox_px[3]) / 2 / page.pixel_size[1] * 100 < high]
    return pages


def _end(pages):
    result = reader.extract(pages)
    return result.history_end, result.history_end_page


def test_history_end_is_confirmed_only_by_a_terminator_after_the_last_entry():
    # 11-26: 순번이 1..N으로 이어져도 마지막 건 아래 끝 표시가 없으면 이력 끝을 확인하지 못한 것이다.
    assert _end(sample.resident()) == ("BLANK_MARKER", 3)
    assert _end(_drop_band(sample.resident(), 2, 37.0, 77.0)) == ("NONE", None)   # 쪽 아래 잘림 (메모 10·11번·이하 여백)
    assert _end(_drop_band(sample.resident(), 2, 43.8, 77.0)) == ("NONE", None)   # 이력은 온전, 끝 표시만 없음
    assert _end(_without_row(sample.resident(), 11)) == ("NONE", None)            # 끝 메모만 남음


def test_history_end_terminator_must_be_standalone_and_last():
    pages = sample.resident()
    marker = next(w for w in pages[2][1].words if "이하 여백" in w.text)
    marker.text = "주소 이하 여백 참고"                                      # 부분 문자열은 끝 표시가 아니다
    assert _end(pages)[0] == "NONE"
    pages = sample.resident()
    x0, y0, x1, y1 = next(w for w in pages[2][1].words if "이하 여백" in w.text).bbox_px
    pages[2][1].words.append(OcrWord("12", .99, (170, y1 + 60, 221, y1 + 106)))   # 끝 표시 아래 순번
    assert _end(pages)[0] == "NONE"


def test_next_section_heading_after_the_last_entry_is_end_evidence():
    pages = sample.resident()
    marker = next(w for w in pages[2][1].words if "이하 여백" in w.text)
    x0, y0, x1, y1 = marker.bbox_px
    marker.text, marker.bbox_px = "병역사항", (170, y0, 330, y1)                   # 순번 칸의 다음 구역 머리글
    assert _end(pages) == ("NEXT_SECTION", 3)
