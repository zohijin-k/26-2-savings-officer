"""S3: an issue date is accepted only next to its label or at a fixed position (synthetic only)."""
from datetime import date, timedelta

import pytest

from engine_v2.extractors import nhis_common
from engine_v2.pipeline.ocr import OcrResult as V2Result, OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tools import doc_timing

from ..ocr.base import OcrResult
from ..ocr.pdftext import VIEWING_COPY_NOTE, read_page_text
from ..rules.doc_check import check_document
from ..rules.doc_types import DocType


def _header(*cells):
    words = [OcrWord(text, .99, (x * 20, 100, x * 20 + 18 * len(text), 130)) for x, text in cells]
    page = PageImage(0, PageSource.UPLOAD, (595.0, 842.0), pixel_size=(2000, 2800))
    return nhis_common.header_for_page(page, V2Result('own', words))


@pytest.mark.parametrize('cells, expected', [
    (((10, '발급일'), (20, '2026-03-10')), date(2026, 3, 10)),
    (((10, '발급'), (14, '일자'), (20, '2026.03.10')), date(2026, 3, 10)),
    (((10, '출력일시'), (20, '2026-04-01')), None),          # print time of a viewing copy
    (((10, '2026-04-01'), (30, '발급일')), None),            # date left of the label
])
def test_issue_date_needs_a_label_on_its_left(cells, expected):
    assert _header(*cells).issue == expected


def _acquisition(**fields):
    base = {'성명': '가상시험', '생년월일': '1990-01-01'}
    base.update(fields)
    issue = fields.get('발급일')
    return OcrResult(detected_doc_type=DocType.NHIS_ACQUISITION_LOSS, confidence=.95, image_quality=.9,
                     tier='localocr', engine='own', fields=base,
                     issue_date=date.fromisoformat(issue) if issue else None)


def test_missing_issue_date_is_reviewed_never_passed():
    req = doc_timing.requirement('NHIS_ACQUISITION_LOSS')
    result = check_document(req, _acquisition())
    assert result.status == 'NEEDS_REVIEW' and 'ISSUE_DATE_MISSING' in result.codes
    assert 'DOCUMENT_ISSUED_TOO_EARLY' not in result.codes


def test_labeled_dates_keep_their_verdicts():
    req = doc_timing.requirement('NHIS_ACQUISITION_LOSS')
    ok = check_document(req, _acquisition(발급일=(req.min_issue_date + timedelta(days=7)).isoformat()))
    assert 'ISSUE_DATE_MISSING' not in ok.codes and 'DOCUMENT_ISSUED_TOO_EARLY' not in ok.codes
    early = check_document(req, _acquisition(발급일=(req.min_issue_date - timedelta(days=30)).isoformat()))
    assert early.status == 'FAIL' and 'DOCUMENT_ISSUED_TOO_EARLY' in early.codes


def test_viewing_copy_mark_is_an_officer_note_only():
    text = '자격득실확인서\n성명 가상시험\n발급일 2026-03-10\n※ 이 문서는 열람용입니다.'
    marked, plain = read_page_text(text, None, 0), read_page_text(text.replace('열람용', '안내용'), None, 0)
    assert VIEWING_COPY_NOTE in marked.quality_note and plain.quality_note == ''
    req = doc_timing.requirement('NHIS_ACQUISITION_LOSS')
    assert check_document(req, marked).status == check_document(req, plain).status
