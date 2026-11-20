"""11-19 T3 (held): the legacy 합계 row is read from the 건강보험료 column of the monthly values.

Before, a 고지금액 group header put the 합계 pick at the group centre (장기요양 or 0원 column) while the
months came from the 건강 sub-column, so 합계 대조 failed and the document went to review. Synthetic only.
"""
import pytest

from engine_v2.extractors import nhis_payment
from engine_v2.tests import test_payment_amount_column as synth


def _checks(pages):
    return {v.name: v.passed for v in nhis_payment.extract(pages).validations}


@pytest.mark.parametrize('zero', [False, True])
@pytest.mark.parametrize('layout, align', [
    ('normal', 'right'), ('short4', 'right'), ('short4', 'center'), ('missing_under', 'right'),
    ('missing_under', 'center'), ('sum_column', 'right'), ('sum_column', 'center'), ('fused4', 'right')])
def test_grouped_total_row_agrees_with_the_health_months(layout, align, zero):
    pages = synth.table(layout, align=align, zero=zero)
    (monthly, _, _, totals, *_), _ = nhis_payment._extract_monthly_detail(pages)
    assert [monthly[(2025, m)][0] for m in (10, 11, 12)] == [synth.HEALTH[m] for m in (10, 11, 12)]
    assert totals == [sum(synth.HEALTH[m] for m in (10, 11, 12))]
    assert _checks(pages)['monthly_total_matches']


def test_single_column_total_is_unchanged():
    pages = synth.table('normal', simple=True)
    (_, _, _, totals, *_), _ = nhis_payment._extract_monthly_detail(pages)
    assert totals == [sum(synth.HEALTH[m] for m in (10, 11, 12))] and _checks(pages)['monthly_total_matches']


def test_unlocated_health_column_reads_no_total_and_no_months():
    pages = synth.table('misread')
    (monthly, _, _, totals, *_), _ = nhis_payment._extract_monthly_detail(pages)
    assert not monthly and not totals
    assert nhis_payment.has_failed_payment_validation(
        {'판독검증실패': ', '.join(n for n, ok in _checks(pages).items() if not ok)})
