"""Member-type value routing: 직장가입·지역가입 phrases send a payment page to the legacy reader."""
from pathlib import Path

import pytest

from engine_v2.extractors import nhis_common as common, nhis_payment, nhis_payment_gov as gov
from engine_v2.tests import p2_payment_samples as p2, p2_shape3_samples as shape3
from engine_v2.tests.p2_form_samples import cell, page
from engine_v2.tests.test_own_adapter_route_diag import canvas, tokens, word
from engine_v2.tests.test_own_adapter_shadow_route import REPRODUCTION, grid_pdf, ocr_case, text_layer
from engine_v2.tests.test_p2_payment_headers import split_words
from engine_v2.tools import batch_assess as batch
from engine_v2.tools import ocr_baseline_fields as fields
from engine_v2.tools import own_adapter_diag_evidence as evidence
from engine_v2.tools import own_adapter_route_diag as route
from engine_v2.tools import own_adapter_shadow_route as shadow
from engine_v2.tools.ocr_baseline_fields import prepare_pairs

PHRASE_Y = 140  # Above the authored header band, so only the phrase differs.


def pairs_of(words):
    return prepare_pairs(canvas(), words, 'own')


def test_operating_and_shadow_definitions_are_identical():
    assert gov.MEMBER_TYPE_NOISE.pattern == shadow.MARKER_NOISE.pattern
    assert gov.MEMBER_TYPE_VALUES == shadow.MARKER_PHRASES['MEMBER_TYPE_VALUE']


@pytest.mark.parametrize('extra,expected', [
    ([('직장가입자', 500)], True),
    ([('지역가입자', 500)], True),
    ([('직장가입', 500)], True),
    ([('직장 가입자', 500)], True),
    ([('직장', 500), ('가입자', 545)], True),
    ([('[직장가입자]', 500)], True),
    ([('(지역가입자)', 500)], True),
    ([('직장·가입자', 500)], True),
    ([('가입구분:지역가입자', 500)], True),
    ([('가입자', 500)], False),
    ([('직장인', 500)], False),
    ([('사업장가입자', 500)], False),
    ([('임의계속가입자', 500)], False),
    ([('지역구분', 500)], False),
    ([('직장가인자', 500)], False),
], ids=['workplace', 'regional', 'stem', 'inner-space', 'two-boxes', 'brackets', 'parentheses', 'middle-dot',
        'label-colon', 'member-only', 'similar-workplace', 'business-member', 'voluntary-member', 'regional-class',
        'misread'])
def test_member_type_normalization_boundaries(extra, expected):
    base = pairs_of(tokens())
    assert gov.recognizes(base) is True and gov.member_type_value(base) is False
    words = tokens() + [word(text, x, PHRASE_Y, width=40 * len(text)) for text, x in extra]
    pairs = pairs_of(words)
    assert gov.member_type_value(pairs) is expected
    assert shadow.member_type_value(pairs) is expected
    assert shadow.legacy_markers(pairs)['MEMBER_TYPE_VALUE'] is expected
    assert gov.recognizes(pairs) is (not expected)
    assert shadow.government(pairs, 'CURRENT') is (not expected)
    assert shadow.government(pairs, 'OLD_CURRENT') is True


@pytest.mark.parametrize('first,second', [('직장', '가입자'), ('지역', '가입자')])
def test_phrase_split_across_lines_is_not_joined(first, second):
    words = tokens() + [word(first, 500, PHRASE_Y - 30, width=40), word(second, 500, PHRASE_Y, width=60)]
    pairs = pairs_of(words)
    assert gov.member_type_value(pairs) is shadow.member_type_value(pairs) is False
    assert gov.recognizes(pairs) is True


def observe(page_image, words, engine):
    found, markers = [], []
    extracted, analysis = route.inspect_extraction(page_image, words, engine, evidence.extract_with_form,
                                                   found, None, markers)
    return extracted[2], found[0], markers[0], analysis


def test_mirror_equals_operating_route_on_render_grid_and_reproductions():
    paths = [text_layer(grid_pdf(font, gap)) + ('text_layer',) for font in (8, 10, 12) for gap in (3.0, 3.5, 4.0, 4.5)]
    paths += [ocr_case(case, engine) + (engine,) for case in sorted(REPRODUCTION) for engine in ('own', 'applevision')]
    for page_image, words, engine in paths:
        form, value, markers, analysis = observe(page_image, words, engine)
        assert form == value['CURRENT'] == markers['rules']['L_MEMBER_TYPE_VALUE'] == 'LEGACY'
        assert analysis['status'] == 'MEASURED' and analysis['flags']['MEMBER_TYPE_ABSENT'] is False


@pytest.mark.parametrize('phrase,expected', [(None, 'GOVERNMENT'), ('직장가입자', 'LEGACY'), ('지역가입자', 'LEGACY')])
def test_mirror_equals_operating_route_on_authored_pages(phrase, expected):
    words = tokens() + ([word(phrase, 500, PHRASE_Y, width=200)] if phrase else [])
    form, value, markers, analysis = observe(canvas(), words, 'own')
    assert form == value['CURRENT'] == markers['rules']['L_MEMBER_TYPE_VALUE'] == expected
    assert value['OLD_CURRENT'] == 'GOVERNMENT'
    assert analysis['status'] == 'MEASURED'
    assert analysis['flags']['GOV_PREDICATE'] is (expected == 'GOVERNMENT')
    assert analysis['flags']['MEMBER_TYPE_ABSENT'] is (phrase is None)


# ---------------------------------------------------------------------------
# Worst case: a genuine government page carrying a member-type phrase is misrouted to
# the legacy reader. The final upload assessment must be NEEDS_REVIEW: PASS would accept an
# unread page and FAIL would wrongly reject a genuine government document.

LABELS = {'고지금액', '납부금액', '건강', '장기요양', '보험료', '보수외', '소득월액'}


def base(name):
    if name.startswith('p2'):
        cells, size = p2.payment(corrected=True)
        options = {'p2-normal': (1, 0, 0), 'p2-skew-plus': (1, 3, 14), 'p2-skew-minus': (1.7, 4, -12)}[name]
        return cells, size, dict(zip(('scale', 'jitter', 'skew'), options))
    cells, size = shape3.document('payment')
    if name == 'shape3-split-horizontal':
        cells = split_words(cells, LABELS, vertical=False)
    elif name == 'shape3-split-vertical':
        cells = split_words(cells, LABELS, vertical=True)
    return cells, size, {}


BASES = ('p2-normal', 'p2-skew-plus', 'p2-skew-minus', 'shape3-normal', 'shape3-split-horizontal',
         'shape3-split-vertical')
POSITIONS = {'top': (.05, .02), 'beside-name': (.75, .17), 'below-table': (.10, .62), 'footer': (.05, .95)}


def assess(pairs):
    path = Path('/__member_type_worst_case__/page.pdf')
    with batch.guarded():
        ocr, _ = batch._read_pages(path, pairs)
        kind = ocr.detected_doc_type.name if ocr.detected_doc_type else 'X'
        return kind, batch._assess(path, kind if kind in batch.KINDS else 'X', ocr)[2]


@pytest.mark.parametrize('name', ('p2-normal', 'p2-skew-minus', 'shape3-split-vertical'))
def test_worst_case_control_without_phrase_is_government_pass(name):
    cells, size, options = base(name)
    pairs = [page(cells, size=size, **options)]
    assert gov.recognizes(pairs) is True
    assert nhis_payment.extract(pairs).form_kind == 'government_payment'
    assert assess(pairs) == ('NHIS_PAYMENT', 'PASS')


@pytest.mark.parametrize('position', sorted(POSITIONS))
@pytest.mark.parametrize('phrase', ('직장가입자', '지역가입자'))
@pytest.mark.parametrize('name', BASES)
def test_worst_case_misrouted_government_page_never_passes(name, phrase, position):
    cells, size, options = base(name)
    assert gov.recognizes([page(cells, size=size, **options)]) is True
    x, y = POSITIONS[position]
    marked = cells + [cell(size[0] * x, size[1] * y, size[0] * x + 200, size[1] * y + 45, phrase, 1)]
    pairs = [page(marked, size=size, **options)]
    assert gov.recognizes(pairs) is False
    assert nhis_payment.extract(pairs).form_kind != 'government_payment'
    kind, status = assess(pairs)
    assert status == 'NEEDS_REVIEW', (kind, status)


def test_reference_table_region_follows_the_new_route():
    cells, size = p2.payment(corrected=True)
    marked = cells + [cell(100, 70, 300, 115, '직장가입자', 1)]
    for source, government in ((cells, True), (marked, False)):
        image, result = page(source, size=size)
        lines = common.page_lines(image, result)
        regions = (fields._government_payment_region(image, result, lines),
                   fields._legacy_payment_region(image, result, lines))
        assert regions[0] != regions[1]
        assert fields.table_region('NHIS_PAYMENT', image, result) == regions[0 if government else 1]
