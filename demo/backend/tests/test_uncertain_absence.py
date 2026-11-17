"""S4: an 'absent' FAIL stands only when the region was read reliably (synthetic text PDFs)."""
import pymupdf

from engine_v2.tools import doc_timing

from ..ocr import read_document
from ..rules.doc_check import UNCERTAIN_ABSENCE_PREFIX, check_document


def _pdf(path, lines):
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        for index, text in enumerate(lines):
            page.insert_text((40, 60 + 18 * index), text, fontsize=9, fontname='korea')
        document.save(path)
    return str(path)


FILLER = '본 증명서는 가상 시험용 합성 문서이며 실제 서류가 아닙니다 ' * 3


def _check(path):
    return check_document(doc_timing.requirement('RESIDENT_ABSTRACT'), read_document(path, None))


def test_truly_absent_history_read_reliably_still_fails(tmp_path):
    result = _check(_pdf(tmp_path / 'absent.pdf', ['주민등록표 ( 초 본 )', '발급일 : 2026년 03월 10일',
                                                    '주소변동내역 : 없음', '번호 주소 발생일 신고일 세대주및관계',
                                                    FILLER, FILLER]))
    finding = next(f for f in result.findings if f.code == 'MISSING_ADDRESS_HISTORY')
    assert result.status == 'FAIL' and finding.severity == 'FAIL'
    assert not finding.message.startswith(UNCERTAIN_ABSENCE_PREFIX)


def test_unread_history_is_reviewed_as_uncertain(tmp_path):
    # Only the title is in the text layer: the table was not read, the date label neither.
    result = _check(_pdf(tmp_path / 'unread.pdf', ['주민등록표 ( 초 본 )',
                                                    '이 초본은 개인별 주민등록표의 기재 내용을 그대로 증명합니다.']))
    finding = next(f for f in result.findings if f.code == 'MISSING_ADDRESS_HISTORY')
    assert finding.severity == 'NEEDS_REVIEW' and finding.message.startswith(UNCERTAIN_ABSENCE_PREFIX)
    assert result.status == 'NEEDS_REVIEW'
    assert {'REQUIRED_FIELD_UNREADABLE', 'LOW_OCR_CONFIDENCE'} & set(result.codes)


def test_documents_with_history_are_unchanged(tmp_path):
    result = _check(_pdf(tmp_path / 'normal.pdf', ['주민등록표 ( 초 본 )', '발급일 : 2026년 03월 10일',
                                                    '번호 주소 발생일 신고일 세대주및관계 변동사유',
                                                    '1 전북특별자치도 전주시 가상동 2020-01-01 전입', FILLER, FILLER]))
    assert 'MISSING_ADDRESS_HISTORY' not in result.codes
    assert not any(f.message.startswith(UNCERTAIN_ABSENCE_PREFIX) for f in result.findings)
