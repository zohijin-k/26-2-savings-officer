"""S4 shadow: an 'absent' FAIL that rests on an unread region becomes NEEDS_REVIEW (synthetic only)."""
import json

import pymupdf

from engine_v2.tools import classify_recovery_diag as tool
from engine_v2.tests.test_classify_recovery_diag import fake_ocr  # noqa: F401


def text_pdf(path, lines):
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        for index, text in enumerate(lines):
            page.insert_text((40, 60 + 18 * index), text, fontsize=9, fontname='korea')
        document.save(path)
    return path


def _rows(out):
    return [json.loads(line) for line in (out / 'rows.jsonl').read_text().splitlines()]


def test_unread_address_table_turns_the_absence_fail_into_review(tmp_path, fake_ocr):
    root = tmp_path / 'root'
    root.mkdir()
    # Page 0 carries only the title; the address table is not in the text layer.
    text_pdf(root / 'a.pdf', ['주민등록표 ( 초 본 )', '이 초본은 개인별 주민등록표의 기재 내용을 그대로 증명합니다.'])
    out = tmp_path / 'out'
    tool.run(root, out)
    (row,) = _rows(out)
    # Production (11-18 S4) already reviews this absence, so the shadow finds no absence FAIL left.
    assert row['form'] == 'RESIDENT_ABSTRACT' and row['decision'] == 'NEEDS_REVIEW'
    assert ['MISSING_ADDRESS_HISTORY', 'NEEDS_REVIEW'] in row['reasons']
    assert row['s4'] is None
    assert 'S4 0 0 0' in (out / 'summary.txt').read_text()


def test_absence_shadow_downgrades_only_with_unreadable_evidence(tmp_path):
    from types import SimpleNamespace
    row = tool.blank_row('0' * 16)
    row['reasons'] = [['MISSING_BILLING_MONTHS', 'FAIL'], ['LOW_OCR_CONFIDENCE', 'NEEDS_REVIEW']]
    row['decision'] = 'FAIL'
    tool.absence_shadow(SimpleNamespace(resident=None), tmp_path / 'x.pdf', row, SimpleNamespace(tier='localocr'))
    assert row['s4']['cooccur'] == 'LOWCONF' and row['s4']['decision'] == 'NEEDS_REVIEW'


def test_confident_absence_keeps_the_fail(tmp_path, fake_ocr):
    root = tmp_path / 'root'
    root.mkdir()
    filler = '본 증명서는 가상 시험용 합성 문서이며 실제 서류가 아닙니다 ' * 3
    text_pdf(root / 'b.pdf', ['주민등록표 ( 초 본 )', '발급일 : 2026년 03월 10일', '주소변동내역 : 없음',
                              '번호 주소 발생일 신고일 세대주및관계', filler, filler])
    out = tmp_path / 'out'
    tool.run(root, out)
    (row,) = _rows(out)
    assert ['MISSING_ADDRESS_HISTORY', 'FAIL'] in row['reasons']
    assert row['s4']['cooccur'] == 'NONE' and row['s4']['decision'] is None
    assert row['s4']['region'] == 'FOUND'
