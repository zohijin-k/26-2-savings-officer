"""g1g2_report aggregation (synthetic stage dictionaries only)."""
from engine_v2.tools import g1g2_report as tool


def _stage(match, fields):
    return dict(type_match=match, fields={key: dict(normalized_match=value) for key, value in fields.items()})


def test_tally_splits_core_items_from_insurance4_and_counts_unclassified_as_wrong():
    stages = [('nhis_payment', _stage('O', {'성명': 'O', '월별고지금액': 'X'})),
              ('insurance_4', _stage('X', {'성명': 'X', '가입내역': 'X'})),
              ('insurance_4', _stage('O', {'성명': 'O', '가입내역': 'X'}))]
    result = tool.tally(stages)
    assert (result['n'], result['g1'], result['g2'], result['g2_items']) == (3, 2, 1, 2)
    assert (result['ins4'], result['ins4_items']) == (1, 4)
    lines = tool.report('presentation', result)
    assert lines[:3] == ['G1 presentation 2/3', 'G2 presentation 1/165 (items 2)',
                         'G2_INS4 presentation 1/25 (items 4)']
    assert 'ITEM presentation insurance_4 가입내역 O 0 X 2' in lines
