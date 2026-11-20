"""T3 (11-19): shadow of reading the legacy 합계 row from the 건강보험료 column (synthetic only).

T3 is applied in production: the diagnostic records T3_APPLIED (after = before, no second read).
The shadow path is still checked on a synthetic pre-T3 reader (``pre_t3``, the substitution
reversed) that reads the 합계 row at the 고지금액 group centre. Codes and counts only.
"""
from types import SimpleNamespace

import pytest

from engine_v2.extractors import nhis_payment
from engine_v2.tests import test_payment_amount_column as synth
from engine_v2.tools import classify_recovery_diag as tool


def _health_total_reader():
    return tool.t3_function()


def _pre_t3_source():
    source = tool._t3_source()
    for old, new, _ in tool.T3_SOURCE:
        source = source.replace(new, old)
    return source


@pytest.fixture
def pre_t3(monkeypatch):
    """Production reader replaced by the pre-T3 source (합계 row at the group centre)."""
    source = _pre_t3_source()
    namespace = dict(vars(nhis_payment))
    exec(compile(source, nhis_payment.__file__, 'exec'), namespace)
    monkeypatch.setattr(nhis_payment, '_extract_monthly_detail', namespace['_extract_monthly_detail'])
    monkeypatch.setattr(tool, '_t3_source', lambda: source)
    assert tool.t3_applied() is False


@pytest.mark.parametrize('layout, align, before, after', [
    ('normal', 'right', 'MATCH', 'MATCH'),
    ('short4', 'right', 'MISMATCH', 'MATCH'),
    ('short4', 'center', 'MISMATCH', 'MATCH'),
    ('missing_under', 'right', 'MISMATCH', 'MATCH'),
    ('sum_column', 'center', 'MISMATCH', 'MATCH'),
    ('fused4', 'right', 'MISMATCH', 'MATCH'),
])
def test_grouped_forms_match_the_total_only_in_the_shadow(pre_t3, layout, align, before, after):
    pages = synth.table(layout, align=align)
    assert tool.t3_total_state(pages) == before
    with tool.t3_patch():
        assert tool.t3_total_state(pages) == after
    assert tool.t3_total_state(pages) == before  # production reader restored


def test_single_column_and_unlocated_health_column_are_unchanged(pre_t3):
    simple = synth.table('normal', simple=True)
    with tool.t3_patch():
        assert tool.t3_total_state(simple) == tool.t3_total_state(simple) == 'MATCH'
    misread = synth.table('misread')
    before = tool.t3_total_state(misread)
    with tool.t3_patch():
        after = tool.t3_total_state(misread)
    assert before == 'MISMATCH' and after == 'NO_TOTAL'


def test_shadow_keeps_the_monthly_values_and_guards(pre_t3):
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


def test_rows_layouts_and_summary(pre_t3):
    rows = [_row(synth.table('short4'), 'NEEDS_REVIEW', 'PASS'), _row(synth.table('normal'), 'PASS', 'PASS'),
            _row(None, 'NEEDS_REVIEW', 'NEEDS_REVIEW')]
    assert rows[0]['t3'] == dict(layout='GROUP_SHORT', before='MISMATCH', after='MATCH', decision='PASS',
                                 applied='X')
    assert rows[2]['t3'] == dict(layout='NA', before='NA', after='NA', decision='NEEDS_REVIEW', applied='NA')
    lines = tool.summarize(rows, dict(counts={}))
    assert 'T3 2 1 2 1 0 1 2 X' in lines
    assert 'T3_DECISION NEEDS_REVIEW PASS 1' in lines and 'T3_DECISION PASS PASS 1' in lines
    assert 'T3_LAYOUT GROUP_SHORT MISMATCH MATCH NEEDS_REVIEW PASS 1' in lines
    for change in (dict(before='free text'), dict(layout='X'), dict(decision='maybe'), dict(applied='yes')):
        with pytest.raises(Exception):
            tool.validate_row(dict(rows[0], t3=dict(rows[0]['t3'], **change)))


# ---------------------------------------------------------------- T3 applied in production


def test_applied_source_is_recognized_and_the_pre_t3_source_is_not():
    assert tool.t3_applied() is True
    assert tool.t3_function() is nhis_payment._extract_monthly_detail
    assert tool.t3_applied(_pre_t3_source()) is False


def test_applied_rows_record_before_as_after_without_a_second_read():
    def no_read(*args):
        raise AssertionError('no shadow read once T3 is applied')
    original = tool._shadow_read
    tool._shadow_read = no_read
    try:
        rows = []
        for layout, decision in (('short4', 'PASS'), ('misread', 'NEEDS_REVIEW')):
            row = tool.blank_row('0' * 16)
            row['form'], row['decision'] = 'NHIS_PAYMENT', decision
            tool.total_row_shadow(SimpleNamespace(payment=(synth.table(layout), None)), 'synthetic.pdf', row)
            tool.validate_row(row)
            rows.append(row)
    finally:
        tool._shadow_read = original
    assert rows[0]['t3'] == dict(layout='GROUP_SHORT', before='MATCH', after='MATCH', decision='PASS', applied='O')
    assert rows[1]['t3'] == dict(layout='GROUP_MISSING', before='NO_TOTAL', after='NO_TOTAL',
                                 decision='NEEDS_REVIEW', applied='O')
    lines = tool.summarize(rows, dict(counts={}))
    assert 'T3 2 1 1 0 0 1 1 O' in lines
    assert 'T3_DECISION PASS PASS 1' in lines and 'T3_DECISION NEEDS_REVIEW NEEDS_REVIEW 1' in lines


# ---------------------------------------------------------------- PAYMENT_COMPONENT (T3 narrowing)


def test_payment_rows_carry_the_component_reason_and_the_summary_counts_it():
    rows = []
    for reason, decision in (('GAP', 'NEEDS_REVIEW'), ('FRAGMENT', 'NEEDS_REVIEW'), (None, 'PASS'),
                             ('free text', 'PASS')):
        pages = synth.table('stacked4')
        row = tool.blank_row('0' * 16)
        row['form'], row['decision'] = 'NHIS_PAYMENT', decision
        fields = {} if reason is None else {'구성머리글불완전사유': reason}
        ocr = SimpleNamespace(fields=fields, page_count=1)
        tool.payment_shadow(SimpleNamespace(payment=(pages, nhis_payment.extract(pages))), 'synthetic.pdf',
                            row, ocr)
        tool.validate_row(row)
        rows.append(row)
    assert [r['payment']['component'] for r in rows] == ['GAP', 'FRAGMENT', 'NONE', 'NONE']
    lines = tool.summarize(rows, dict(counts={}))
    assert 'PAYMENT_COMPONENT reason decision n' in lines
    assert 'PAYMENT_COMPONENT GAP NEEDS_REVIEW 1' in lines and 'PAYMENT_COMPONENT FRAGMENT NEEDS_REVIEW 1' in lines
    assert 'PAYMENT_COMPONENT NONE PASS 2' in lines
    with pytest.raises(Exception):
        tool.validate_row(dict(rows[0], payment=dict(rows[0]['payment'], component='free text')))
