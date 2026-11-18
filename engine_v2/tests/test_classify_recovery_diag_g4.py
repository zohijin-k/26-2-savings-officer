"""G4 (11-19): payment 고지금액 guard flags and table layout, counts and verdicts only (synthetic only)."""
from types import SimpleNamespace

import pytest

from engine_v2.extractors import nhis_payment
from engine_v2.tests import test_payment_amount_column as synth
from engine_v2.tools import classify_recovery_diag as tool


def _row(pages, decision='PASS'):
    result = nhis_payment.extract(pages)
    fields = {key: str(value.value) for key, value in result.fields.items()}
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'] = 'NHIS_PAYMENT', decision
    tool.amount_guard_check(SimpleNamespace(payment=(pages, result)), row, SimpleNamespace(fields=fields))
    tool.validate_row(row)
    return row


@pytest.mark.parametrize('pages, layout, flags', [
    (synth.table('normal'), 'GROUP_HEALTH', ('X', 'X', 'X', 'X')),
    (synth.table('short4'), 'GROUP_SHORT', ('X', 'X', 'X', 'X')),
    (synth.table('fused'), 'GROUP_FUSED', ('X', 'X', 'CARE', 'X')),
    (synth.table('misread'), 'GROUP_MISSING', ('X', 'X', 'X', 'X')),
    (synth.table('normal', simple=True), 'SINGLE_MISSING', ('X', 'X', 'X', 'X')),
    (synth.table('normal', simple=True, rows={11: [0]}), 'SINGLE_MISSING', ('O', 'X', 'X', 'X')),
    (synth.table('normal', simple=True, rows={11: [13_000]}, paid_health=100_000), 'SINGLE_MISSING',
     ('X', 'O', 'X', 'X')),
    (synth.table('normal', simple=True, header_conf=.5), 'SINGLE_MISSING', ('X', 'X', 'UNCERTAIN', 'X')),
    (synth.table('normal', paid_health=150_000), 'GROUP_HEALTH', ('X', 'X', 'X', 'O')),
])
def test_layout_and_flags(pages, layout, flags):
    g4 = _row(pages)['g4']
    assert (g4['layout'], (g4['zero'], g4['ratio'], g4['header'], g4['larger'])) == (layout, flags)


def test_not_extracted_payment_is_na():
    row = tool.blank_row('0' * 16)
    tool.amount_guard_check(SimpleNamespace(payment=None), row, SimpleNamespace(fields={}))
    tool.validate_row(row)
    assert row['g4'] == dict(layout='NA', zero='X', ratio='X', header='X', larger='X')


def test_summary_counts_flags_layouts_and_decisions():
    rows = [_row(synth.table('normal')), _row(synth.table('normal', simple=True, rows={11: [0]}), 'NEEDS_REVIEW')]
    lines = tool.summarize(rows, dict(counts={}))
    assert 'G4 2 1 0 0 0 1' in lines
    assert 'G4_LAYOUT GROUP_HEALTH X 1' in lines and 'G4_LAYOUT SINGLE_MISSING O 1' in lines
    assert 'G4_DECISION SINGLE_MISSING O NEEDS_REVIEW 1' in lines and 'G4_DECISION GROUP_HEALTH X PASS 1' in lines


def test_rows_reject_free_text():
    row = _row(synth.table('normal'))
    for key, value in (('layout', 'free text'), ('zero', 'yes'), ('header', 'HEADER_CARE')):
        with pytest.raises(Exception):
            tool.validate_row(dict(row, g4=dict(row['g4'], **{key: value})))
