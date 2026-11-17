"""L2: a fixed January–December legacy payment table under a query-period title.

Synthetic only. The title says "2025년 10월 ~ 2025년 12월 납부내역"; the table always prints
twelve month-only rows (1월~12월), a year-end settlement row and a total row; only the query
months carry amounts. The billing months must follow the title year and the query range.
"""
import json

import pymupdf
import pytest

from engine_v2.tools.documentai_synth import Source, pdf_bytes


def calendar_pdf(path, *, outside_amount=0, period="2025년 10월 ~ 2025년 12월 납부내역"):
    font = 9
    cells = [(170, 60, '건강보험료 납부확인서', 14), (50, 110, '성명', font), (150, 110, '가상시험', font),
             (320, 110, '생년월일', font), (420, 110, '1990.01.01', font), (50, 140, '직장가입자', font),
             (150, 180, period, font)]
    cells += [(x, 215, text, font) for x, text in ((50, '월별'), (180, '고지금액'), (360, '납부금액'))]
    total = 0
    for month in range(1, 13):
        amount = 50000 if month >= 10 else outside_amount
        total += amount
        cells += [(x, 235 + (month - 1) * 22, text, font)
                  for x, text in ((50, f'{month}월'), (180, f'{amount:,}'), (360, f'{amount:,}'))]
    cells += [(x, 235 + 12 * 22, text, font) for x, text in ((50, '연말정산'), (180, '0'), (360, '0'))]
    cells += [(x, 235 + 13 * 22, text, font) for x, text in ((50, '합계'), (180, f'{total:,}'), (360, f'{total:,}'))]
    cells += [(150, 600, '위와 같이 납부하였음을 확인합니다.', font), (220, 630, '2026년 03월 03일', font),
              (200, 660, '국민건강보험공단', font)]
    path.write_bytes(pdf_bytes(Source('nhis_payment', [(cells, (595, 842))], {}, {})))
    return path


def _pages(path):
    from engine_v2.pipeline.ocr import OcrResult, OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    with pymupdf.open(path) as document:
        page = document[0]
        scale = 300 / 72
        words = [OcrWord(item[4], 1.0, tuple(v * scale for v in item[:4]))
                 for item in page.get_text('words', sort=True) if item[4].strip()]
        image = PageImage(0, PageSource.TEXT_LAYER, (page.rect.width, page.rect.height),
                          pixel_size=(int(page.rect.width * scale), int(page.rect.height * scale)), dpi=300)
    return [(image, OcrResult('text_layer', words))]


def test_title_year_and_query_range_define_billing_months(tmp_path):
    from engine_v2.extractors import nhis_payment
    result = nhis_payment.extract(_pages(calendar_pdf(tmp_path / 'calendar.pdf')))
    assert result.fields['고지월'].value == '2025-10,2025-11,2025-12'
    assert sorted(json.loads(result.fields['월별고지금액'].value)) == ['2025-10', '2025-11', '2025-12']
    assert result.fields['건강보험료'].value == '50000'
    checks = {check.name: check.passed for check in result.validations}
    assert checks['months_continuous'] and checks['monthly_total_matches'] and checks['paid_total_matches']


def test_positive_amount_outside_the_query_range_is_never_absorbed(tmp_path):
    from engine_v2.extractors import nhis_payment
    result = nhis_payment.extract(_pages(calendar_pdf(tmp_path / 'calendar.pdf', outside_amount=1000)))
    assert result.fields['고지월'].value == '2025-10,2025-11,2025-12'
    # The printed total includes the out-of-range amounts, so arithmetic cannot confirm the table.
    checks = {check.name: check.passed for check in result.validations}
    assert not checks['monthly_total_matches']


def test_period_crossing_a_year_keeps_the_next_year_for_earlier_months(tmp_path):
    from engine_v2.extractors import nhis_payment
    path = calendar_pdf(tmp_path / 'calendar.pdf', period='2025년 10월 ~ 2026년 9월 납부내역')
    result = nhis_payment.extract(_pages(path))
    months = result.fields['고지월'].value.split(',')
    assert months[0] == '2025-10' and months[-1] == '2026-09' and len(months) == 12


def test_upload_reading_reports_only_query_months(tmp_path):
    from demo.backend.ocr import read_document
    ocr = read_document(str(calendar_pdf(tmp_path / 'calendar.pdf')), None)
    assert ocr.detected_doc_type is not None and ocr.detected_doc_type.name == 'NHIS_PAYMENT'
    assert ocr.fields['고지월'] == '2025-10,2025-11,2025-12'
