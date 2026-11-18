"""T3 (11-19): shadow of reading the legacy 합계 row from the 건강보험료 column (synthetic only).

Production keeps reading the 합계 row at the 고지금액 group centre; the shadow applies the held
change in memory and reports the 합계 check and the verdict after it. Codes and counts only.
"""
from types import SimpleNamespace

import pytest

from engine_v2.extractors import nhis_payment
from engine_v2.tests import test_payment_amount_column as synth
from engine_v2.tools import classify_recovery_diag as tool


def _health_total_reader():
    return tool.t3_function()


@pytest.mark.parametrize('layout, align, before, after', [
    ('normal', 'right', 'MATCH', 'MATCH'),
    ('short4', 'right', 'MISMATCH', 'MATCH'),
    ('short4', 'center', 'MISMATCH', 'MATCH'),
    ('missing_under', 'right', 'MISMATCH', 'MATCH'),
    ('sum_column', 'center', 'MISMATCH', 'MATCH'),
    ('fused4', 'right', 'MISMATCH', 'MATCH'),
])
def test_grouped_forms_match_the_total_only_in_the_shadow(layout, align, before, after):
    pages = synth.table(layout, align=align)
    assert tool.t3_total_state(pages) == before
    with tool.t3_patch():
        assert tool.t3_total_state(pages) == after
    assert tool.t3_total_state(pages) == before  # production reader restored


def test_single_column_and_unlocated_health_column_are_unchanged():
    simple = synth.table('normal', simple=True)
    with tool.t3_patch():
        assert tool.t3_total_state(simple) == tool.t3_total_state(simple) == 'MATCH'
    misread = synth.table('misread')
    before = tool.t3_total_state(misread)
    with tool.t3_patch():
        after = tool.t3_total_state(misread)
    assert before == 'MISMATCH' and after == 'NO_TOTAL'


def test_shadow_keeps_the_monthly_values_and_guards():
    for layout in ('normal', 'short4', 'fused4', 'misread'):
        pages = synth.table(layout)
        base, base_guard = nhis_payment._extract_monthly_detail(pages)
        shadow, shadow_guard = _health_total_reader()(pages)
        assert shadow[0] == base[0] and shadow_guard == base_guard
        assert shadow[4] == base[4] and shadow[5] == base[5]  # paid months and paid totals


def test_changed_source_is_reported_not_guessed(monkeypatch):
    monkeypatch.setattr(tool, 'T3_SOURCE', tool.T3_SOURCE + (('no such line', 'x', 1),))
    with pytest.raises(RuntimeError, match='T3_SOURCE_CHANGED'):
        tool.t3_function()


def _row(pages, decision, shadow_decision):
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'] = 'NHIS_PAYMENT', decision
    reader = SimpleNamespace(detected_doc_type=None)
    trace = SimpleNamespace(payment=(pages, None))
    original_read, original_assess = tool._shadow_read, tool._assess
    tool._shadow_read = lambda *args: reader
    tool._assess = lambda *args: (shadow_decision, [])
    try:
        tool.total_row_shadow(trace, 'synthetic.pdf', row)
    finally:
        tool._shadow_read, tool._assess = original_read, original_assess
    tool.validate_row(row)
    return row


def test_rows_layouts_and_summary():
    rows = [_row(synth.table('short4'), 'NEEDS_REVIEW', 'PASS'), _row(synth.table('normal'), 'PASS', 'PASS'),
            _row(None, 'NEEDS_REVIEW', 'NEEDS_REVIEW')]
    assert rows[0]['t3'] == dict(layout='GROUP_SHORT', before='MISMATCH', after='MATCH', decision='PASS')
    assert rows[2]['t3'] == dict(layout='NA', before='NA', after='NA', decision='NEEDS_REVIEW')
    lines = tool.summarize(rows, dict(counts={}))
    assert 'T3 2 1 2 1 0 1 2' in lines
    assert 'T3_DECISION NEEDS_REVIEW PASS 1' in lines and 'T3_DECISION PASS PASS 1' in lines
    assert 'T3_LAYOUT GROUP_SHORT MISMATCH MATCH NEEDS_REVIEW PASS 1' in lines
    for change in (dict(before='free text'), dict(layout='X'), dict(decision='maybe')):
        with pytest.raises(Exception):
            tool.validate_row(dict(rows[0], t3=dict(rows[0]['t3'], **change)))
