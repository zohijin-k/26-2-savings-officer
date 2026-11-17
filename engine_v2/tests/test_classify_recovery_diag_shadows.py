"""Synthetic-only checks of the 11-18 diagnostics: compare, D1 ARITH codes, C2, A2 and A4 shadows."""
import json

import pymupdf
import pytest

from engine_v2.tools import classify_recovery_diag as tool
from engine_v2.tools.documentai_synth import Source, pdf_bytes
from engine_v2.tests.test_classify_recovery_diag import PAYMENT_TITLE, SENTINEL, build, fake_ocr  # noqa: F401

NOTICE = '※ 직장가입자의 보수월액보험료 납부의무자는 「국민건강보험법」 제77조에 따라 사업장의 사용자입니다.'


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


def payment_cells(member='지역가입자', *, notice=True, total=None, settlement=None, months=(100, 110, 120)):
    f = 8
    cells = [(170, 60, '건강보험료 납부확인서', 14), (50, 110, '성명', f), (150, 110, '가상시험', f),
             (320, 110, '생년월일', f), (420, 110, '1990.01.01', f)]
    if member:
        cells.append((50, 140, member, f))
    cells += [(150, 180, '2025년 10월 ~ 2025년 12월 납부내역', f),
              (50, 210, '월별', f), (200, 210, '고지금액', f), (380, 210, '납부금액', f)]
    for index, (month, amount) in enumerate(zip((10, 11, 12), months)):
        y = 235 + index * 22
        cells += [(50, y, f'2025.{month}', f), (200, y, f'{amount},000', f), (380, y, f'{amount},000', f)]
    y = 235 + 3 * 22
    if settlement is not None:
        cells += [(50, y, '연말정산', f), (200, y, f'{settlement},000', f), (380, y, f'{settlement},000', f)]
        y += 22
    printed = sum(months) if total is None else total
    cells += [(50, y, '합계', f), (200, y, f'{printed},000', f), (380, y, f'{printed},000', f)]
    cells += [(150, 600, '위와 같이 납부하였음을 확인합니다.', f), (200, 640, '국민건강보험공단', f)]
    if notice:
        cells.append((40, 700, NOTICE, 7))
    return cells


# ---------------------------------------------------------------- A4


def test_footer_notice_makes_production_member_type_work_and_the_candidate_ignores_it():
    from engine_v2.extractors import nhis_payment
    pages = _pages(payment_cells('지역가입자'))
    assert nhis_payment.extract(pages).fields['가입구분'].value == '직장'  # production reads the notice
    assert tool.member_type_candidate(pages) == '지역'
    assert tool.member_type_candidate(_pages(payment_cells(None))) == 'X'          # no evidence: empty
    assert tool.member_type_candidate(_pages(payment_cells('직장가입자'))) == '직장'
    assert tool.member_type_candidate(_pages(payment_cells('직장가입자', notice=False))) == '직장'


def test_workplace_label_followed_by_another_label_is_not_evidence():
    cells = payment_cells(None) + [(50, 160, '사업장명칭', 8), (150, 160, '납부자번호', 8)]
    assert tool.member_type_candidate(_pages(cells)) == 'X'
    cells = payment_cells(None) + [(50, 160, '사업장명칭', 8), (150, 160, '가상연구사업장', 8)]
    assert tool.member_type_candidate(_pages(cells)) == '직장'


# ---------------------------------------------------------------- D1


@pytest.mark.parametrize('kwargs, diff', [
    (dict(total=330 + 30, settlement=30), 'NA'),                       # settlement included: arithmetic holds
    (dict(total=330, settlement=30), 'DIFF_EQ_SETTLE'),               # printed total excludes settlement
    (dict(total=330 - 110), 'DIFF_EQ_ONE_MONTH'),
    (dict(total=999), 'SUM_LT_TOTAL'),
    (dict(total=1), 'SUM_GT_TOTAL'),
])
def test_arith_causes_name_the_difference_without_values(kwargs, diff):
    pages = _pages(payment_cells('지역가입자', **kwargs))
    codes = tool.arith_causes(pages, 'LEGACY', 'ARITH')
    assert codes['arith_diff'] == diff
    assert set(codes) == set(tool.ARITH_KEYS)
    assert all(isinstance(value, str) and not any(ch.isdigit() for ch in value if value not in tool.ARITH_TOTALS)
               for value in codes.values())
    if diff == 'DIFF_EQ_SETTLE':
        assert codes['arith_settle'] == 'O' and codes['arith_check'] == 'BOTH'
    assert tool.arith_causes(pages, 'GOV', 'ARITH') == {key: 'NA' for key in tool.ARITH_KEYS}


# ---------------------------------------------------------------- C2


def test_c2_turns_only_the_quality_fail_into_review_for_every_form():
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules import doc_check
    from demo.backend.rules.doc_types import DocType
    original = doc_check.engine_image_quality_status
    req = tool.timing.requirement('NHIS_QUALIFICATION')

    def finalize(code, doc_type=DocType.NHIS_QUALIFICATION):
        ocr = OcrResult(detected_doc_type=doc_type, confidence=.9, image_quality=.5)
        result = doc_check.CheckResult('NEEDS_REVIEW', [doc_check.CheckFinding(code, 'x', severity='NEEDS_REVIEW')])
        return doc_check.finalize_image_quality(req, ocr, result, 'pdf').status
    assert finalize('REQUIRED_FIELD_UNREADABLE') == 'FAIL'
    assert finalize('UNKNOWN_DOCUMENT_TYPE', None) == 'FAIL'
    with tool.c2_patch():
        assert finalize('REQUIRED_FIELD_UNREADABLE') == 'NEEDS_REVIEW'
        assert finalize('UNKNOWN_DOCUMENT_TYPE', None) == 'NEEDS_REVIEW'
    assert doc_check.engine_image_quality_status is original


# ---------------------------------------------------------------- A2


def test_a2_patch_feeds_300dpi_renderings_and_restores_production(tmp_path):
    from engine_v2 import engine as v2engine
    from engine_v2.pipeline import preprocess as v2pre
    path = build(tmp_path / 'low.pdf', 'plain')
    original = v2pre.preprocess
    assert original(path)[0].source.value == 'embedded'
    with tool.a2_patch():
        pages = v2pre.preprocess(path)
        assert v2engine.preprocess is v2pre.preprocess
    assert pages[0].source.value == 'render' and pages[0].dpi == 300
    assert v2pre.preprocess is original and v2engine.preprocess is original


def test_run_rows_carry_the_new_shadow_keys(tmp_path, fake_ocr):
    root = tmp_path / 'root'
    root.mkdir()
    build(root / 'a.pdf', 'plain')
    out = tmp_path / 'out'
    assert tool.run(root, out) == 0
    (row,) = [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]
    assert row['form'] == 'NHIS_PAYMENT' and row['a4'] is not None and row['shadow_errors'] == []
    summary = (out / 'summary.txt').read_text()
    for header in ('A2 tried', 'A4_CHANGE', 'C2_FAIL_TO_REVIEW', 'PAYMENT_ARITH'):
        assert header in summary


# ---------------------------------------------------------------- compare


def test_compare_crosses_two_doc_timing_runs_by_key(tmp_path, fake_ocr, capsys):
    from engine_v2.tools import doc_timing
    root = tmp_path / 'FAKE-input'
    (root / f'{SENTINEL}-folder').mkdir(parents=True)
    build(root / f'{SENTINEL}-folder' / f'{SENTINEL}-a.pdf', 'plain')
    build(root / f'{SENTINEL}-folder' / f'{SENTINEL}-b.pdf', 'plain')
    doc_timing.run(root, tmp_path / 'one', warmup=0)
    fake_ocr['title'] = ('아무', '관련', '없는', '글')
    doc_timing.run(root, tmp_path / 'two', warmup=0)
    capsys.readouterr()
    assert tool.main(['compare', '--before', str(tmp_path / 'one' / 'rows.jsonl'),
                      '--after', str(tmp_path / 'two' / 'rows.jsonl')]) == 0
    printed = capsys.readouterr().out
    assert 'COMPARE 2 2 2 0 0' in printed
    assert 'FORM NHIS_PAYMENT X 2' in printed
    assert 'CHANGED' in printed and 'ROOT_MISMATCH' not in printed
    assert SENTINEL not in printed and str(tmp_path) not in printed
    assert tool.main(['compare', '--before', str(tmp_path / 'missing.jsonl'),
                      '--after', str(tmp_path / 'two' / 'rows.jsonl')]) == 2
