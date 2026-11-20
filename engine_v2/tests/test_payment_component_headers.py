"""11-19 T3 narrowing: a partly read 보수외소득월액 sub-header under a legacy group header (synthetic only).

With the 합계 row read from the 건강 column, a damaged sub-header no longer fails arithmetic. The
legacy reader records 구성머리글불완전사유 when a column shows a fragment ('보수외', '소득월액',
'(건강)', '(요양)') that does not read as one known label (FRAGMENT) or has a lost line (GAP, BOTH).
Only GAP and BOTH mark 구성머리글상태=불완전; FRAGMENT alone is recorded only (real government forms
routed to the legacy reader misread one 보수외 box). The government-form reader and complete grouped
forms are unchanged.
"""
import pytest

from engine_v2.extractors import nhis_payment, nhis_payment_gov
from engine_v2.tests import p2_payment_samples as sample, test_payment_amount_column as synth
from engine_v2.tests.p2_form_samples import page


def _without(pages, text, count=1):
    (_, result), = pages
    removed = [w for w in result.words if w.text == text][:count]
    assert len(removed) == count
    result.words = [w for w in result.words if all(w is not r for r in removed)]
    return pages


def _government(lost=0):
    cells, size = sample.payment()
    kept, removed = [], 0
    for cell in cells:
        if cell[4] == "소득월액" and removed < lost:
            removed += 1
        else:
            kept.append(cell)
    return [page(kept, size=size)]


def _state(pages):
    field = nhis_payment.extract(pages).fields.get("구성머리글상태")
    return field.value if field else None


def _reason(pages):
    field = nhis_payment.extract(pages).fields.get("구성머리글불완전사유")
    assert nhis_payment.component_header_issue(pages) == (field.value if field else None)
    return field.value if field else None


@pytest.mark.parametrize("layout", ["normal", "short", "short4", "missing_under", "stacked4", "fused", "fused4",
                                    "sum_column"])
def test_complete_grouped_legacy_forms_are_unchanged(layout):
    pages = synth.table(layout)
    assert not nhis_payment_gov.recognizes(pages)
    assert not nhis_payment.component_headers_incomplete(pages) and _state(pages) is None


@pytest.mark.parametrize("layout, text", [("stacked4", "보수외"), ("stacked4", "(건강)"), ("stacked4", "(요양)"),
                                          ("missing_under", "(건강)")])
def test_one_lost_fragment_is_recorded_only(layout, text):
    pages = _without(synth.table(layout), text)
    assert not nhis_payment_gov.recognizes(pages)
    # 11-19: FRAGMENT alone no longer marks 구성머리글상태; the reason field still records it.
    assert not nhis_payment.component_headers_incomplete(pages) and _state(pages) is None
    assert _reason(pages) == "FRAGMENT"


def test_one_truncated_fragment_is_recorded_only():
    pages = synth.table("short4")
    next(w for w in pages[0][1].words if w.text == "보수외(건강)").text = "보수외(건"
    assert _state(pages) is None and _reason(pages) == "FRAGMENT"


@pytest.mark.parametrize("misread", ["보수의", "보수"])
def test_government_form_with_misread_outside_boxes_records_fragment_only(misread):
    # Real government forms: own OCR reads a whole '보수외' box only once or twice per page, so the
    # form misses the eight-column signature and goes to the legacy reader. The 보수외소득월액(요양)
    # columns read '보수의 / 소득월액 / (요양)': a FRAGMENT, while the 합계 row still agrees.
    cells, size = sample.payment()
    seen = 0
    for index, cell in enumerate(cells):
        if cell[4] == "보수외":
            if seen % 2:
                cells[index] = cell[:4] + (misread,) + cell[5:]
            seen += 1
    pages = [page(cells, size=size)]
    assert not nhis_payment_gov.recognizes(pages)
    result = nhis_payment.extract(pages)
    assert _reason(pages) == "FRAGMENT" and _state(pages) is None
    assert not nhis_payment.component_headers_incomplete(pages)
    assert {v.name: v.passed for v in result.validations}["monthly_total_matches"]


@pytest.mark.parametrize("lost", [2, 3, 4])
def test_lost_middle_lines_route_to_legacy_and_are_incomplete(lost):
    pages = _government(lost)
    assert not nhis_payment_gov.recognizes(pages)
    assert nhis_payment.component_headers_incomplete(pages) and _state(pages) == "불완전"
    # '보수외' / blank / '(건강)' reads as the known short label 보수외(건강): only the lost line shows.
    assert _reason(pages) == "GAP"


def test_lost_line_and_unknown_fragment_together_are_both():
    pages = _government(2)
    next(w for w in reversed(pages[0][1].words) if w.text == "(요양)").text = "(요"
    assert _reason(pages) == "BOTH"


@pytest.mark.parametrize("layout", ["normal", "short4", "stacked4"])
def test_complete_forms_have_no_reason(layout):
    assert _reason(synth.table(layout)) is None


@pytest.mark.parametrize("lost", [0, 1])
def test_government_reader_path_is_unchanged(lost):
    pages = _government(lost)
    assert nhis_payment_gov.recognizes(pages)
    assert "구성머리글상태" not in nhis_payment.extract(pages).fields


def test_single_column_form_is_not_checked():
    pages = synth.table("normal", simple=True)
    assert not nhis_payment.charge_grouped(pages) and _state(pages) is None
