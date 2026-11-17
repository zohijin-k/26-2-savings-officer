"""S3 shadow: where the issue date came from (synthetic text-layer pages only)."""
import pymupdf
import pytest

from engine_v2.tools import classify_recovery_diag as tool
from engine_v2.tools.documentai_synth import Source, pdf_bytes


def _pages(cells):
    from engine_v2.pipeline.ocr import OcrResult, OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    data = pdf_bytes(Source('nhis_acquisition_loss', [(cells, (595, 842))], {}, {}))
    with pymupdf.open(stream=data, filetype='pdf') as document:
        page, scale = document[0], 300 / 72
        words = [OcrWord(i[4], 1.0, tuple(v * scale for v in i[:4]))
                 for i in page.get_text('words', sort=True) if i[4].strip()]
        image = PageImage(0, PageSource.TEXT_LAYER, (page.rect.width, page.rect.height),
                          pixel_size=(int(page.rect.width * scale), int(page.rect.height * scale)), dpi=300)
    return [(image, OcrResult('text_layer', words))]


def acquisition(*extra):
    f = 8
    cells = [(170, 60, '자격득실 확인서', 14), (50, 110, '성명', f), (150, 110, '가상시험', f),
             (50, 200, '자격취득일', f), (200, 200, '자격상실일', f),
             (50, 222, '2026-04-01', f), (200, 222, '2026-05-01', f)]
    return _pages(cells + list(extra))


@pytest.mark.parametrize('extra, value, source', [
    ([(300, 140, '발급일', 8), (360, 140, '2026-03-10', 8)], '2026-03-10', 'LABEL'),
    ([(360, 140, '발급일', 8), (300, 140, '2026-03-10', 8)], '2026-03-10', 'LABEL_LEFT'),
    ([(300, 140, '출력일시', 8), (360, 140, '2026-03-10', 8)], '2026-03-10', 'OUTPUT_LABEL'),
    ([(150, 600, '위와 같이 확인합니다.', 8), (200, 630, '2026-03-10', 8), (200, 660, '국민건강보험공단 이사장', 8)],
     '2026-03-10', 'CONFIRM_BAND'),
    ([], '2026-04-01', 'OTHER'),            # a table date used as the issue date
    ([], None, 'NONE'),
])
def test_issue_source_classes(extra, value, source):
    assert tool.issue_source('NHIS_ACQUISITION_LOSS', acquisition(*extra), value) == source


def test_text_route_and_resident_header_band():
    assert tool.issue_source('NHIS_QUALIFICATION', None, '2026-03-10') == 'LABEL_TEXT'
    pages = _pages([(300, 40, '2026년 03월 10일', 8), (100, 300, '본문', 8)])
    assert tool.issue_source('RESIDENT_ABSTRACT', pages, '2026-03-10') == 'HEADER_BAND'


def test_fallback_issue_dates_are_reassessed_without_the_date(tmp_path):
    from types import SimpleNamespace
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType
    pages = acquisition()
    ocr = OcrResult(detected_doc_type=DocType.NHIS_ACQUISITION_LOSS, confidence=.95, tier='localocr',
                    fields={'성명': '가상시험', '생년월일': '1990-01-01', '발급일': '2026-04-01'})
    path = tmp_path / 'a.pdf'
    path.write_bytes(b'%PDF-1.7')
    row = tool.blank_row('0' * 16)
    row['form'] = 'NHIS_ACQUISITION_LOSS'
    row['decision'], row['reasons'] = tool._assess(path, row['form'], ocr)
    tool.issue_shadow(SimpleNamespace(read_pages=pages), path, row, ocr)
    assert row['s3']['source'] == 'OTHER' and row['s3']['yeollam'] == 'X'
    # Without the table date the document can never pass on its issue date.
    assert row['s3']['decision'] in ('NEEDS_REVIEW', 'FAIL')
    tool.validate_row(row)
    labeled = tool.blank_row('0' * 16)
    labeled['form'] = 'NHIS_ACQUISITION_LOSS'
    tool.issue_shadow(SimpleNamespace(read_pages=acquisition((300, 140, '발급일', 8), (360, 140, '2026-04-01', 8))),
                      path, labeled, ocr)
    assert labeled['s3'] == dict(source='LABEL', yeollam='X', decision=None)


def test_yeollam_mark_is_counted():
    pages = acquisition((40, 760, '※ 이 문서는 열람용입니다.', 8))
    assert tool._yeollam(pages, None) == 'O'
    assert tool._yeollam(acquisition(), None) == 'X'
