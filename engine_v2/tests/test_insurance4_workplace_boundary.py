"""4대보험 general-path column boundary between 사업장관리번호 and 사업장명칭 (synthetic words)."""
import pytest

from engine_v2.extractors import insurance_4
from engine_v2.pipeline.layout import Word

ANCHORS = {"name": 23.0, "category": 34.0, "management": 48.0, "workplace": 65.0, "date": 82.0}


def _word(text, x0, width=5.0):
    return Word(text, .99, 0, x0, 35.0, x0 + width, 36.0, (0, 0, 0, 0))


def _row(*cells, portal=False):
    words = [_word("국민연금", 9.0), _word("가상가가", 23.0), _word("사업장가입자", 34.0),
             *(_word(text, x0) for text, x0 in cells), _word("2020.01.01", 82.0)]
    return insurance_4._parse_row("국민연금", [words], ANCHORS, portal=portal)


@pytest.mark.parametrize("offset", [.1, .5, 1.0])
def test_name_starting_slightly_left_of_its_label_is_the_workplace_name(offset):
    row = _row(("00000000000", 48.0), ("가짜상사", 65.0 - offset), ("가짜", 71.0))
    assert row.workplace_name == "가짜상사가짜"
    assert row.management_number == "00000000000"


@pytest.mark.parametrize("x0", [56.6, 63.0, 64.9])
def test_management_number_near_the_boundary_stays_a_management_number(x0):
    row = _row(("12345678901", x0), ("가짜상사", 65.0))
    assert row.management_number == "12345678901" and row.workplace_name == "가짜상사"


def test_fragment_left_of_the_midpoint_is_not_taken_as_a_name():
    row = _row(("00000000000", 48.0), ("가짜", 52.0), ("상사", 65.0))
    assert row.workplace_name == "상사"
