"""D8: address-history ordinal state of resident abstracts, counts and verdicts only (synthetic only)."""
from types import SimpleNamespace

import pytest

from engine_v2.tests.p2_resident_samples import damage, resident
from engine_v2.tools import classify_recovery_diag as tool


def _row(pages, decision='PASS'):
    row = tool.blank_row('0' * 16)
    row['form'], row['decision'] = 'RESIDENT_ABSTRACT', decision
    tool.history_check(SimpleNamespace(resident=pages), row)
    tool.validate_row(row)
    return row


@pytest.mark.parametrize('pages, numbers, empty', [
    (resident(), 'CONTIGUOUS', 'X'),
    (damage(resident(), 'note'), 'GAP', 'X'),
    (damage(resident(), 'unreadable'), 'UNREADABLE', 'X'),
    (None, 'NA', 'NA'),
])
def test_history_states(pages, numbers, empty):
    assert _row(pages)['history'] == dict(numbers=numbers, empty_page=empty)


def test_summary_counts_states_and_decisions():
    rows = [_row(resident()), _row(damage(resident(), 'note'), 'NEEDS_REVIEW')]
    lines = tool.summarize(rows, dict(counts={}))
    assert 'D8 2 1 1 0 0' in lines
    assert 'D8_DECISION GAP X NEEDS_REVIEW 1' in lines and 'D8_DECISION CONTIGUOUS X PASS 1' in lines
