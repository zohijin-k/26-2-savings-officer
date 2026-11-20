"""11-19 T3 (held): a grouped legacy 납부확인서 read from the 건강 column passes once its 합계 agrees.

장기요양·0원 picks and unlocated 건강 columns still go to review (synthetic only).
"""
import pytest

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tests import test_payment_amount_column as synth

from .test_payment_amount_column import CODE, _income, _monthly, _upload


def _marked(pages):
    """The same synthetic table with a printed 1/1 folio and a 2025.10~12 query period (the printed months)."""
    (page, result), = pages
    next(word for word in result.words if word.text == '01월').text = '10월'
    result.words.append(OcrWord('1/1', 1.0, (1220, 3300, 1290, 3340)))
    return pages


@pytest.mark.parametrize('zero', [False, True])
@pytest.mark.parametrize('layout, align', [('normal', 'right'), ('short4', 'right'), ('short4', 'center'),
                                           ('missing_under', 'right'), ('sum_column', 'right'),
                                           ('sum_column', 'center')])
def test_grouped_form_with_a_matching_total_passes(tmp_path, layout, align, zero):
    ocr, result = _upload(tmp_path, _marked(synth.table(layout, align=align, zero=zero)))
    assert _monthly(ocr) == synth._health()
    assert result.status == 'PASS', result.codes
    facts, income = _income(ocr, result)
    assert facts.monthly_premium == round(sum(synth.HEALTH[m] for m in (10, 11, 12)) / 3)


@pytest.mark.parametrize('kwargs', [
    dict(layout='short4', rows={11: [0, 0, 0, 0]}),                     # 0원 picked in the 건강 column
    dict(layout='normal', simple=True, rows={11: [0]}),                  # 0원 in a single column
    dict(layout='normal', simple=True, rows={11: [13_000]}, paid_health=100_000),  # 장기요양-sized pick
    dict(layout='fused4', align='center'),                               # fused 건강+장기요양 header
    dict(layout='misread'),                                              # 건강 column not located
])
def test_care_or_zero_picks_and_unlocated_columns_still_need_review(tmp_path, kwargs):
    ocr, result = _upload(tmp_path, _marked(synth.table(**kwargs)))
    assert result.status == 'NEEDS_REVIEW', result.codes
    assert _income(ocr, result)[1].status == 'UNDETERMINED'
