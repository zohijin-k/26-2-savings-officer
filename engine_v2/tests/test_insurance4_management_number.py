"""4대보험 가입내역 사업장관리번호 reading variants (synthetic words, fictitious values).

The general (government24/unknown) path keeps a management number only as printed:
a number centred under the narrower 관리번호 label, hyphenated, spaced, split over two
lines or fused with the workplace name is read; lookalike letters are never converted
and leave the cell blank with 사업장관리번호상태 불확실. Other columns stay as read.
The portal path keeps its strict 11-digit cell check (an unreadable cell stays review).
"""
import json
from datetime import date

import pytest

from engine_v2.extractors import insurance_4
from engine_v2.pipeline.layout import Word
from engine_v2.tests.nhis_form_samples import NAME, coordinate_page, insurance_portal_cells

NUMBER = "12345678901"
ROWS = (36, 40, 44, 48)
ANCHORS = {"name": 23.0, "category": 34.0, "management": 48.0, "workplace": 65.0, "date": 82.0}

VARIANTS = {
    "plain": lambda y: [(48, y, NUMBER)],
    "hyphen": lambda y: [(48, y, "123-45-67890-1")],
    "unicode_dash": lambda y: [(48, y, "123–45–67890–1")],
    "spaced_one_box": lambda y: [(48, y, "123 45 67890 1")],
    "spaced_boxes": lambda y: [(48, y, "123"), (51, y, "45"), (53, y, "67890"), (58, y, "1")],
    "two_lines": lambda y: [(48, y, "123456"), (48, y + .9, "78901")],
    "left_of_label_0.5": lambda y: [(47.5, y, NUMBER)],
    "left_of_label_1.5": lambda y: [(46.5, y, NUMBER)],
    "centred_hyphen": lambda y: [(46, y, "123-45-67890-1")],
}
UNCERTAIN = {
    "O_for_0": lambda y: [(48, y, "123456789O1")],
    "l_for_1": lambda y: [(48, y, NUMBER.replace("1", "l"))],
    "ten_digits": lambda y: [(48, y, "1234567890")],
    "other_mark": lambda y: [(48, y, "12345.678901")],
}


def _cells(form, numbers, *, drop_name=False):
    cells = []
    for x, y, text in insurance_portal_cells():
        if x == 48 and y in ROWS:
            cells += numbers(y)
        elif not (drop_name and x == 65 and y in ROWS):
            cells.append((x, y, text))
    cells = [cell for cell in cells if cell[2] != "확인용"]
    if form == "government24":
        cells.append((10, 60, "문서확인번호 1234-5678-9012-3456"))
    return cells


def _extract(cells):
    return insurance_4.extract([coordinate_page(cells)], today=date(2026, 11, 13))


def _other_columns_intact(result):
    assert [row.insurance_type for row in result.rows] == list(insurance_4.INSURANCE_NAMES)
    assert all(row.status == "가입" and row.subscriber_name == NAME for row in result.rows)
    assert [row.subscriber_category for row in result.rows] == ["사업장가입자", "직장가입자", "직장가입자", "직장가입자"]
    assert all(row.acquired == date(2020, 1, 1) and row.received == date(2020, 1, 2) for row in result.rows)
    assert json.loads(result.fields["보험별가입여부"].value) == dict.fromkeys(insurance_4.INSURANCE_NAMES, True)


@pytest.mark.parametrize("form", ["government24", "unknown"])
@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_general_path_reads_printed_management_number_variants(form, variant):
    result = _extract(_cells(form, VARIANTS[variant]))
    assert result.form_kind == form
    assert [row.management_number for row in result.rows] == [NUMBER] * 4
    assert all(row.workplace_name.replace(" ", "") == "가짜상사가짜" for row in result.rows)
    assert not any(row.management_uncertain for row in result.rows)
    assert "사업장관리번호상태" not in result.fields["가입내역"].value
    _other_columns_intact(result)


@pytest.mark.parametrize("form", ["government24", "unknown"])
def test_number_fused_with_the_workplace_name_is_split(form):
    result = _extract(_cells(form, lambda y: [(48, y, NUMBER + "가짜상사가짜")], drop_name=True))
    assert [row.management_number for row in result.rows] == [NUMBER] * 4
    assert [row.workplace_name for row in result.rows] == ["가짜상사가짜"] * 4
    _other_columns_intact(result)


@pytest.mark.parametrize("form", ["government24", "unknown"])
@pytest.mark.parametrize("variant", sorted(UNCERTAIN))
def test_doubtful_management_number_is_blank_and_uncertain_not_guessed(form, variant):
    result = _extract(_cells(form, UNCERTAIN[variant]))
    assert [row.management_number for row in result.rows] == [""] * 4
    assert all(row.management_uncertain for row in result.rows)
    rows = json.loads(result.fields["가입내역"].value)
    assert [row["사업장관리번호"] for row in rows] == [""] * 4
    assert [row["사업장관리번호상태"] for row in rows] == ["불확실"] * 4
    assert all(row.workplace_name.replace(" ", "") == "가짜상사가짜" for row in result.rows)
    _other_columns_intact(result)


def test_doubtful_management_number_does_not_change_the_government24_checks():
    plain = _extract(_cells("government24", VARIANTS["plain"]))
    doubtful = _extract(_cells("government24", UNCERTAIN["O_for_0"]))
    assert [(v.name, v.passed) for v in plain.validations] == [(v.name, v.passed) for v in doubtful.validations]
    assert doubtful.structure_complete is plain.structure_complete is None
    for key in ("근로관련가입여부", "근로관련최초취득일", "근로관련최근취득일", "보험별가입자종별", "사업장명칭목록"):
        assert doubtful.fields[key].value == plain.fields[key].value


def _word(text, x0, width=5.0):
    return Word(text, .99, 0, x0, 35.0, x0 + width, 36.0, (0, 0, 0, 0))


def _row(*cells, portal=False):
    words = [_word("국민연금", 9.0), _word("가상가가", 23.0), _word("사업장가입자", 34.0),
             *(_word(text, x0, width) for text, x0, width in cells), _word("2020.01.01", 82.0)]
    return insurance_4._parse_row("국민연금", [words], ANCHORS, portal=portal)


def test_digit_word_left_of_the_label_needs_its_centre_in_the_column():
    assert _row((NUMBER, 45.0, 8.8)).management_number == NUMBER  # centre 49.4
    row = _row((NUMBER, 40.0, 6.0))  # centre 43.0: not this column, nothing guessed
    assert row.management_number == "" and not row.management_uncertain


def test_workplace_name_with_digits_past_the_midpoint_stays_a_name():
    row = _row((NUMBER, 48.0, 8.8), ("제2공장", 63.0, 4.0), ("가짜", 66.0, 3.0))
    assert row.management_number == NUMBER and row.workplace_name == "제2공장가짜"


@pytest.mark.parametrize("variant", ["hyphen", "centred_hyphen"])
def test_portal_path_keeps_its_strict_cell_check(variant):
    cells = [(x, y, t) for x, y, t in _cells("portal", VARIANTS[variant])] + [(10, 16, "확인용")]
    result = _extract(cells)
    assert result.form_kind == "portal"
    assert result.structure_complete is False
    assert [row.management_number for row in result.rows] == [""] * 4
    assert all(row.management_uncertain for row in result.rows)
