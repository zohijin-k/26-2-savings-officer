"""A3: an unread 건강보험료 cell must never be replaced by the 장기요양보험료 cell (synthetic only)."""
import json

import pymupdf
import pytest

from engine_v2.tools.documentai_synth import Source, pdf_bytes

HEALTH, CARE = '79,100', '10,240'


def _pages(cells):
    from engine_v2.pipeline.ocr import OcrResult, OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    data = pdf_bytes(Source('nhis_payment', [(cells, (595, 842))], {}, {}))
    with pymupdf.open(stream=data, filetype='pdf') as document:
        page, scale = document[0], 300 / 72
        words = [OcrWord(i[4], 1.0, tuple(v * scale for v in i[:4]))
                 for i in page.get_text('words', sort=True) if i[4].strip()]
        image = PageImage(0, PageSource.TEXT_LAYER, (page.rect.width, page.rect.height),
                          pixel_size=(int(page.rect.width * scale), int(page.rect.height * scale)), dpi=300)
    return [(image, OcrResult('text_layer', words))]


def two_level_table(unread_health_rows=(), unread_health_total=False):
    """고지금액·납부금액 group headers over 건강보험료 / 장기요양보험료 columns."""
    f = 8
    cells = [(170, 60, '건강보험료 납부확인서', 14), (50, 110, '성명', f), (150, 110, '가상시험', f),
             (150, 180, '2025년 10월 ~ 2025년 12월 납부내역', f),
             (50, 210, '월별', f), (200, 205, '고지금액', f), (400, 205, '납부금액', f),
             (150, 222, '건강보험료', f), (250, 222, '장기요양보험료', f), (350, 222, '건강보험료', f),
             (450, 222, '장기요양보험료', f)]
    for index, month in enumerate((10, 11, 12)):
        y = 245 + index * 22
        cells += [(50, y, f'2025.{month}', f), (250, y, CARE, f), (350, y, HEALTH, f), (450, y, CARE, f)]
        if month not in unread_health_rows:
            cells.append((150, y, HEALTH, f))
    cells += [(50, 320, '합계', f), (250, 320, '30,720', f), (350, 320, '237,300', f), (450, 320, '30,720', f)]
    if not unread_health_total:
        cells.append((150, 320, '237,300', f))
    cells += [(150, 600, '위와 같이 납부하였음을 확인합니다.', f), (200, 660, '국민건강보험공단', f)]
    return _pages(cells)


@pytest.mark.parametrize('rows, total', [((10,), False), ((10, 11, 12), False), ((10, 11, 12), True)])
def test_unread_health_cells_never_take_the_care_column(rows, total):
    from engine_v2.extractors import nhis_payment
    result = nhis_payment.extract(two_level_table(rows, total))
    monthly = json.loads(result.fields['월별고지금액'].value) if '월별고지금액' in result.fields else {}
    assert '10240' not in monthly.values()
    assert '건강보험료' not in result.fields
    # A failed review validation keeps the premium out of the income decision (facts._payment_amounts_trusted).
    assert nhis_payment.has_failed_payment_validation(
        {'판독검증실패': ', '.join(c.name for c in result.validations if not c.passed)})


def test_all_unread_health_column_and_total_cannot_confirm_arithmetic():
    from engine_v2.extractors import nhis_payment
    result = nhis_payment.extract(two_level_table((10, 11, 12), True))
    checks = {check.name: check.passed for check in result.validations}
    assert not checks['monthly_amounts_numeric']
