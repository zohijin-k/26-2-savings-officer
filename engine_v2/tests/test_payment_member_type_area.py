"""A4 (held): 가입구분 never comes from the footer notice (synthetic only)."""
import pymupdf

from engine_v2.extractors import nhis_payment
from engine_v2.tools.documentai_synth import Source, pdf_bytes

NOTICE = '※ 직장가입자의 보수월액보험료 납부의무자는 「국민건강보험법」 제77조에 따라 사업장의 사용자입니다.'


def _pages(member, notice=True, extra=()):
    from engine_v2.pipeline.ocr import OcrResult, OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    f = 8
    cells = [(170, 60, '건강보험료 납부확인서', 14), (50, 110, '성명', f), (150, 110, '가상시험', f),
             (150, 180, '2025년 10월 ~ 2025년 12월 납부내역', f), (50, 210, '월별', f), (200, 210, '고지금액', f)]
    if member:
        cells.append((50, 140, member, f))
    cells += list(extra)
    for i, month in enumerate((10, 11, 12)):
        cells += [(50, 235 + 22 * i, f'2025.{month}', f), (200, 235 + 22 * i, '100,000', f)]
    cells += [(150, 600, '위와 같이 납부하였음을 확인합니다.', f), (200, 640, '국민건강보험공단', f)]
    if notice:
        cells.append((40, 700, NOTICE, 7))
    data = pdf_bytes(Source('nhis_payment', [(cells, (595, 842))], {}, {}))
    with pymupdf.open(stream=data, filetype='pdf') as document:
        page, scale = document[0], 300 / 72
        words = [OcrWord(i[4], 1.0, tuple(v * scale for v in i[:4])) for i in page.get_text('words', sort=True) if i[4].strip()]
        image = PageImage(0, PageSource.TEXT_LAYER, (page.rect.width, page.rect.height),
                          pixel_size=(int(page.rect.width * scale), int(page.rect.height * scale)), dpi=300)
    return [(image, OcrResult('text_layer', words))]


def _member(pages):
    field = nhis_payment.extract(pages).fields.get('가입구분')
    return field.value if field else None


def test_local_member_with_the_footer_notice_stays_local():
    assert _member(_pages('지역가입자')) == '지역'


def test_no_evidence_leaves_the_member_type_empty():
    assert _member(_pages(None)) is None


def test_work_member_is_read_from_the_personal_area():
    assert _member(_pages('직장가입자')) == '직장'
    assert _member(_pages(None, extra=[(50, 160, '사업장명칭', 8), (150, 160, '가상연구사업장', 8)])) == '직장'
    assert _member(_pages(None, extra=[(50, 160, '사업장명칭', 8), (150, 160, '납부자번호', 8)])) is None
