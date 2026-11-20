"""11-19: 월별고지금액 must come from the 건강보험료 column, never 장기요양 (synthetic only).

Two real 납부확인서 (2025-10~12) gave the 장기요양 amount (about 13% of 건강보험료) or its 0원 cell.
Reproduced: a 고지금액 group header over several sub-columns whose 건강 sub-header was not located
(short '건강', '보험료' missing under it, misread, fused with 장기요양, extra '계' column). The group
centre was then used as the column and falls on the 장기요양 column; the 합계 row read the same column,
so arithmetic agreed. Root fix: locate the 건강 sub-column or give no value. Separate guard: a 0원 pick,
a pick 12-14% of another amount in its row, a pick under a 장기요양 or unreadable header, or a larger
amount under a 건강 header marks 월별고지금액 불확실 (values unchanged).
"""
import json

import pytest

from engine_v2.extractors import nhis_payment, nhis_payment_gov
from engine_v2.pipeline.ocr import OcrResult, OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource

W, H = 2480, 3508
HEALTH = {m: 100000 + m * 1000 for m in range(1, 13)}
TARGET = ("2025-10", "2025-11", "2025-12")


def _care(month, zero):
    return 0 if zero else round(HEALTH[month] * .1295)


def _word(text, x, y, align='left', conf=1.0):
    width = sum(22 if ch.isdigit() or ch in ',.-()' else 38 for ch in text)
    x0 = {'left': x, 'right': x - width, 'center': x - width / 2}[align]
    return OcrWord(text, conf, (x0, y, x0 + width, y + 40))


LAYOUTS = {
    'normal': ['건강보험료', '장기요양보험료'],
    'short': ['건강', '장기요양'],
    'short4': ['건강', '장기요양', '보수외(건강)', '보수외(요양)'],
    'missing_under': [('건강', None), ('장기요양', '보험료'), ('보수외', '(건강)'), ('보수외', '(요양)')],
    'stacked4': [('건강', '보험료'), ('장기요양', '보험료'), ('보수외', '(건강)'), ('보수외', '(요양)')],
    'fused': ['건강보험료장기요양보험료'],
    'fused4': ['건강보험료장기요양보험료', '보수외(건강)', '보수외(요양)'],
    'misread': ['건깅보험료', '장기요양보험료'],
    'sum_column': ['건강', '장기요양', '계'],
}


def table(layout, *, zero=False, align='right', rows=None, header_conf=1.0, paid_health=None, simple=False):
    """Legacy (공단) form: 고지금액·납부금액 groups over component columns, or one 고지금액 column."""
    cols = LAYOUTS[layout] if not simple else ['']
    fused = layout.startswith('fused')
    ncomp = 1 if simple else 2 if layout == 'fused' else 4 if layout == 'fused4' else len(cols)
    colw, x_month, x_start, top = 230, 150, 420, 560
    words = [_word('건강보험료', 900, 150), _word('납부확인서', 1150, 150), _word('성명', 150, 300),
             _word('가상시험', 400, 300), _word('생년월일', 1200, 300), _word('1999.01.01', 1450, 300),
             _word('가입구분', 150, 360), _word('직장가입자', 400, 360),
             _word('2025년', 400, 450), _word('01월', 560, 450), _word('~', 660, 450), _word('2025년', 700, 450),
             _word('12월', 860, 450), _word('납부내역', 960, 450), _word('월별', x_month, top + 60)]
    for group, name in enumerate(('고지금액', '납부금액')):
        g0 = x_start + group * ncomp * colw
        words.append(_word(name, g0 + ncomp * colw / 2, top, 'center', conf=header_conf if group == 0 else 1.0))
        if simple:
            continue
        if fused:
            words.append(_word(cols[0], g0 + colw, top + 60, 'center'))
            words += [_word(n, g0 + k * colw + colw / 2, top + 60, 'center') for k, n in enumerate(cols[1:], 2)]
            continue
        for k, n in enumerate(cols):
            cx = g0 + k * colw + colw / 2
            for dy, part in zip((60, 110), n if isinstance(n, tuple) else (n,)):
                if part:
                    words.append(_word(part, cx, top + dy, 'center'))

    def put(values, y):
        for group, row in enumerate(values):
            g0 = x_start + group * ncomp * colw
            for k, v in enumerate(row):
                edge = g0 + (k + 1) * colw - 20 if align == 'right' else g0 + k * colw + colw / 2
                words.append(_word(f'{v:,}', edge, y, 'right' if align == 'right' else 'center'))

    y, sums = top + 200, None
    for month in range(10, 13):
        h, c = HEALTH[month], _care(month, zero)
        billed = (rows or {}).get(month) or (
            [h] if simple else [h, c, h + c] if layout == 'sum_column' else
            [h, c, 0, 0] if ncomp == 4 else [h, c])
        paid = list(billed)
        if paid_health is not None:
            paid[0] = paid_health
        words.append(_word(f'2025.{month:02d}', x_month, y))
        put([billed, paid], y)
        sums = [[a + b for a, b in zip(s, r)] for s, r in zip(sums, [billed, paid])] if sums else [billed, paid]
        y += 60
    words.append(_word('합계', x_month, y))
    put(sums, y)
    words += [_word('위와', 300, y + 300), _word('같이', 420, y + 300), _word('납부하였음을', 540, y + 300),
              _word('확인합니다.', 900, y + 300), _word('2026년', 800, y + 400), _word('11월', 980, y + 400),
              _word('10일', 1110, y + 400), _word('국민건강보험공단', 900, y + 500)]
    return [(PageImage(0, PageSource.TEXT_LAYER, (595, 842), pixel_size=(W, H), dpi=300),
             OcrResult('text_layer', words))]


def _read(pages):
    assert not nhis_payment_gov.recognizes(pages)
    result = nhis_payment.extract(pages)
    fields = {k: v.value for k, v in result.fields.items()}
    monthly = json.loads(fields['월별고지금액']) if '월별고지금액' in fields else {}
    failed = ', '.join(v.name for v in result.validations if not v.passed)
    return fields, [monthly.get(m) for m in TARGET], nhis_payment.has_failed_payment_validation({'판독검증실패': failed})


def _health():
    return [str(HEALTH[m]) for m in (10, 11, 12)]


def _care_values(zero):
    return [str(_care(m, zero)) for m in (10, 11, 12)]


# ---------------------------------------------------------------- reproduced causes, root fix


@pytest.mark.parametrize('zero', [False, True])
@pytest.mark.parametrize('layout, align', [
    ('short', 'center'), ('short4', 'right'), ('short4', 'center'), ('missing_under', 'right'),
    ('missing_under', 'center'), ('sum_column', 'right'), ('sum_column', 'center'),
    ('fused', 'center'), ('fused4', 'right'), ('fused4', 'center')])
def test_group_without_a_located_health_column_now_reads_the_health_column(layout, align, zero):
    fields, picked, _ = _read(table(layout, zero=zero, align=align))
    assert picked == _health()
    assert picked != _care_values(zero)


@pytest.mark.parametrize('zero', [False, True])
@pytest.mark.parametrize('align', ['right', 'center'])
def test_misread_health_header_gives_no_value_instead_of_the_care_column(align, zero):
    fields, picked, review = _read(table('misread', zero=zero, align=align))
    assert picked == [None, None, None]
    assert review and '건강보험료' not in fields


@pytest.mark.parametrize('zero', [False, True])
def test_fused_health_care_header_reads_health_but_stays_uncertain(zero):
    fields, picked, _ = _read(table('fused', zero=zero, align='right'))
    assert picked == _health()
    assert fields['월별고지금액상태'] == '불확실' and 'HEADER_CARE' in fields['월별고지금액불확실사유']


@pytest.mark.parametrize('layout, align', [('normal', 'right'), ('short', 'right')])
def test_normal_forms_are_unchanged_and_carry_no_guard(layout, align):
    for zero in (False, True):
        fields, picked, review = _read(table(layout, zero=zero, align=align))
        assert picked == _health() and not review
        assert '월별고지금액상태' not in fields and fields['건강보험료'] == '111000'


def test_simple_single_column_form_carries_no_guard():
    fields, picked, review = _read(table('normal', simple=True))
    assert picked == _health() and not review and '월별고지금액상태' not in fields


# ---------------------------------------------------------------- guard a-d (values never replaced)


def _guarded(pages, code):
    fields, picked, _ = _read(pages)
    assert fields['월별고지금액상태'] == '불확실'
    assert code in fields['월별고지금액불확실사유'].split(',')
    return picked


def test_guard_a_zero_pick():
    picked = _guarded(table('normal', simple=True, rows={11: [0]}), 'ZERO_AMOUNT')
    assert picked[1] == '0'  # kept as read; the decision is withheld, not the value replaced


def test_guard_b_pick_is_12_to_14_percent_of_another_amount_in_its_row():
    # One 고지금액 column; the 납부금액 cell of that row is 100,000 (13% → as a 장기요양 pick would be).
    picked = _guarded(table('normal', simple=True, rows={11: [13_000]}, paid_health=100_000), 'CARE_RATIO')
    assert picked[1] == '13000'


def test_guard_c_care_header_over_the_pick():
    _guarded(table('fused', align='right'), 'HEADER_CARE')


def test_guard_c_uncertain_header_over_the_pick():
    _guarded(table('normal', simple=True, header_conf=.5), 'HEADER_UNCERTAIN')


def test_guard_d_larger_amount_under_a_health_header():
    _guarded(table('normal', paid_health=150_000), 'LARGER_HEALTH')


def test_guard_reasons_unit():
    assert nhis_payment.amount_guard_reasons(100_000, [12_950, 100_000]) == set()
    assert nhis_payment.amount_guard_reasons(0, [100_000]) == {'ZERO_AMOUNT'}
    assert nhis_payment.amount_guard_reasons(12_950, [100_000]) == {'CARE_RATIO'}
    assert nhis_payment.amount_guard_reasons(15_000, [100_000]) == set()
    health, outside, care = [_word('건강', 0, 0)], [_word('보수외', 0, 0), _word('건강', 0, 0)], [_word('장기요양', 0, 0)]
    assert nhis_payment.amount_guard_reasons(100, [200], [], [health]) >= {'LARGER_HEALTH'}
    # 보수외소득월액(건강) and 장기요양 columns are not 건강보험료 columns.
    assert 'LARGER_HEALTH' not in nhis_payment.amount_guard_reasons(100, [200, 300], [], [outside, care])
    # A negative pick (refund/adjustment row; income rejects it already) is not compared.
    assert 'LARGER_HEALTH' not in nhis_payment.amount_guard_reasons(-500, [0], [], [health])


# ---------------------------------------------------------------- government eight-column form


def test_government_form_normal_carries_no_guard():
    from engine_v2.tests.test_p2_payment import extraction
    result = extraction(corrected=False, optional=False, paid_different=False)
    assert '월별고지금액상태' not in result.fields


@pytest.mark.parametrize('row, code', [
    ([0, 0, None, None, 0, 0, None, None], 'ZERO_AMOUNT'),
    ([13_000, 1_300, 100_000, None, 13_000, 1_300, None, None], 'CARE_RATIO'),
    ([20_000, 2_000, None, None, 40_000, 4_000, None, None], 'LARGER_HEALTH')])
def test_government_form_guard(row, code):
    values = [[100_000, 10_000, None, None, 100_000, 10_000, None, None] for _ in range(12)]
    values[10] = row
    fields = {}
    nhis_payment_gov._put_amount_guard(fields, values, 2025, [], 0, {}, {})
    assert fields['월별고지금액상태'].value == '불확실'
    assert code in fields['월별고지금액불확실사유'].value.split(',')
    # No readable header lines → the header family check is uncertain as well.
    assert 'HEADER_UNCERTAIN' in fields['월별고지금액불확실사유'].value
