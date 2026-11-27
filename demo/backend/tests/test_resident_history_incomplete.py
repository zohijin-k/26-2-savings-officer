"""11-18: missed address-history rows make 전입일 uncertain instead of passing (synthetic only).

Ordinals must run 1..N without a gap (memo lines carry their own ordinal), and a page whose address
table header was found must yield at least one history row.
"""
import json

import pytest

from engine_v2.extractors import resident_abstract
from engine_v2.tests.p2_resident_samples import damage, resident
from engine_v2.tests.test_resident_abstract import header, row, table_head, wd

from .run_p18_applicant_precheck_scenarios import IDENTITY, final_page_end
from .test_resident_blank_pages import _read
from .scan_guard import scan_guard_off  # noqa: F401 (fixture)

# Subject: other resident logic; the 11-26 scan guard is tested in test_resident_scan_guard.py.
pytestmark = pytest.mark.usefixtures("scan_guard_off")

APPLICANT = f"신청인: {IDENTITY.name} ({IDENTITY.birth.isoformat()})"


def _page(marker, rows):
    words = header(1, 1, name=IDENTITY.name, applicant=APPLICANT)
    for word in words:
        if word.text == "1/1":
            word.text = marker
    return words + table_head(31.8) + rows + final_page_end(marker)


OLD = [*row(34.4, 1, "전북특별자치도 전주시 가상동", "2020-01-01"), *row(39.4, 2, "전북특별자치도 전주시 합성동", "2021-01-01")]
RECENT = [*row(34.4, 3, "서울특별시 가상구 시험동", "2022-01-01"), *row(39.4, 4, "전북특별자치도 군산시 가상동", "2023-01-01")]


def _uncertain(ocr, result, reasons):
    assert result.status == "NEEDS_REVIEW" and "ADDRESS_HISTORY_INCOMPLETE" in result.codes
    assert ocr.fields["주소이력상태"] == "불확실" and ocr.fields["주소이력불확실사유"] == reasons
    assert ocr.fields["전입일"] == "불확실" and ocr.fields["주소이력건수"] == "불확실"
    assert "전입일" not in ocr.bboxes


def test_first_page_rows_missed_is_reviewed(tmp_path):
    ocr, result = _read(tmp_path, [_page("1/2", []), _page("2/2", RECENT)])
    # 11-27 공통 동기화: youth 신호 NUMBER_START(읽은 번호가 1로 시작하지 않음)도 같은 결함을 따로 알린다.
    _uncertain(ocr, result, "NUMBER_GAP,EMPTY_PAGE,NUMBER_START")


def test_recent_page_rows_missed_never_yields_an_early_transfer_date(tmp_path):
    # Without the recent page the 전북 run would start at 2020-01-01 (earlier than the real 2023-01-01).
    ocr, result = _read(tmp_path, [_page("1/2", OLD), _page("2/2", [])])
    _uncertain(ocr, result, "EMPTY_PAGE,END_UNCONFIRMED")  # 11-26: 마지막으로 읽힌 건 아래 끝 표시 없음


def test_recent_page_rows_without_readable_dates_are_reviewed(tmp_path):
    garbled = [wd(9.1, 35.3, "3", 1.0, 2), wd(13.2, 34.4, "서울특별시 가상구 시험동", 1.0, 35),
               wd(67.9, 34.4, "2O22-O1-O1", 1.0, 9)]
    ocr, result = _read(tmp_path, [_page("1/2", OLD), _page("2/2", garbled)])
    # 11-26: 마지막으로 읽힌 건 아래 끝 표시 없음. 11-27: 날짜를 못 읽은 3번 줄의 번호가 보임(UNREAD_ROWS).
    _uncertain(ocr, result, "EMPTY_PAGE,UNREAD_ROWS,END_UNCONFIRMED")


def test_complete_ordinals_are_unchanged(tmp_path):
    ocr, result = _read(tmp_path, [_page("1/2", OLD), _page("2/2", RECENT)])
    assert result.status == "PASS" and "ADDRESS_HISTORY_INCOMPLETE" not in result.codes
    assert "주소이력상태" not in ocr.fields
    assert ocr.fields["전입일"] == "2023-01-01" and ocr.fields["주소이력건수"] == "4"


def test_memo_lines_and_blank_space_keep_the_history_complete():
    ex = resident_abstract.extract(resident())  # memo lines 8 and 10 carry their own ordinals, then 이하 여백
    assert ex.history_numbers == "CONTIGUOUS" and not ex.history_empty_page


@pytest.mark.parametrize("defect, state", [
    ("first", "UNREADABLE"), ("middle", "UNREADABLE"), ("unreadable", "UNREADABLE"),  # number not read
    ("note", "GAP"), ("duplicate", "GAP"),                                             # number missing
])
def test_number_unreadable_and_number_gap_are_separate_reasons(defect, state):
    assert resident_abstract.extract(damage(resident(), defect)).history_numbers == state


def test_page_data_is_unchanged_by_the_history_check(tmp_path):
    ocr, _ = _read(tmp_path, [_page("1/2", OLD), _page("2/2", [])])
    assert json.loads(ocr.fields["쪽표기자료"])["markers"] == [[1, 2], [2, 2]]
