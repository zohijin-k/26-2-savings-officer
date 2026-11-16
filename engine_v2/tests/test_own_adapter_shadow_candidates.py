"""Shadow candidates A_325/A_350/B/L, D3 position bins and the legacy-only marker (diagnostic only)."""
from copy import deepcopy
import json

import pytest

from engine_v2.extractors import nhis_payment_gov as gov
from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tools import own_adapter_diag as tool
from engine_v2.tools import own_adapter_diag_evidence as evidence
from engine_v2.tools import own_adapter_route_diag as route
from engine_v2.tools import own_adapter_shadow_route as shadow
from engine_v2.tools.ocr_baseline_fields import prepare_pairs
from engine_v2.tests.test_own_adapter_route_diag import (
    SENTINEL, assert_private_output, canvas, install_payment, invoke, locations, tokens, word)  # noqa: F401
from engine_v2.tests.test_own_adapter_shadow_route import (
    REPRODUCTION, grid_pdf, observe, ocr_case, text_layer)

ALL = (*shadow.RULES, *shadow.CANDIDATES)


def capture(page, words, engine):
    found, extra = [], []
    extracted, _ = route.inspect_extraction(page, words, engine, evidence.extract_with_form, found, extra)
    assert len(found) == len(extra) == 1
    return extracted[2], {**found[0], **extra[0]['rules']}, extra[0]['measures']


def decide(pairs):
    return {**{rule: 'GOVERNMENT' if shadow.government(pairs, rule) else 'LEGACY' for rule in shadow.RULES},
            **{rule: 'GOVERNMENT' if shadow.candidate_government(pairs, rule) else 'LEGACY'
               for rule in shadow.CANDIDATES}}


def pairs_of(words):
    return prepare_pairs(canvas(), words, 'own')


def code(value):
    return ''.join(value[rule][0] for rule in ALL)


# Rule order: CURRENT OLD_CURRENT A S A_325 A_350 B L A_325+L A_350+L (G = GOVERNMENT, L = LEGACY).
# The grid and its reproductions carry 직장가입자, so CURRENT is LEGACY; candidates keep the OLD_CURRENT base.
GRID_TEXT = {3.0: 'LGGLGGLGGG', 3.5: 'LGGLGGLGGG', 4.0: 'LGGLGGLGGG', 4.5: 'LLLLLGLLLG'}
REPRODUCED = {('own', 4): 'LGLLGGLGGG', ('own', 8): 'LGLLLLLGLL', ('own', 12): 'LGLLLLLGLL',
              ('applevision', 4): 'LLLLLGLLLG', ('applevision', 8): 'L' * 10, ('applevision', 12): 'L' * 10}


@pytest.mark.parametrize('font', (8, 10, 12))
@pytest.mark.parametrize('gap', (3.0, 3.5, 4.0, 4.5))
def test_render_grid_text_layer_candidates(font, gap):
    form, value, measures = capture(*text_layer(grid_pdf(font, gap)), 'text_layer')
    assert value['CURRENT'] == form
    assert code(value) == GRID_TEXT[gap]
    assert measures['MARKER'] == 'X'


@pytest.mark.parametrize('case', sorted(REPRODUCTION))
@pytest.mark.parametrize('engine', ('own', 'applevision'))
def test_actual_ocr_reproductions_under_candidates(case, engine):
    form, value, measures = capture(*ocr_case(case, engine), engine)
    assert value['CURRENT'] == form
    assert code(value) == REPRODUCED[(engine, case)]
    assert measures['MARKER'] == 'X'


def test_a300_is_an_alias_of_a_and_l_alias_is_current_plus_marker():
    assert dict(shadow.ALIASES) == {'A_300': 'A', 'CURRENT+L': 'L'}
    for header_y in (190, 200, 215, 220, 225, 230, 235, 238):
        words = tokens(header_y=header_y, month_height=10)
        geometry = shadow._geometry(pairs_of(words))
        assert shadow._band(3.0)(*geometry) == shadow.SELECTIONS['A'](*geometry)
        marked = words + [word('가입구분', 500, 100)]
        assert shadow.candidate_government(pairs_of(words), 'L') is shadow.government(pairs_of(words), 'CURRENT')
        assert shadow.candidate_government(pairs_of(marked), 'L') is False


@pytest.mark.parametrize('header_y,expected', [
    # H = 10 px, first-month centre 255 px, phrase centre header_y + 5: distance (250 - header_y) / 10 H.
    (221, 'GGG'), (219, 'LGG'), (217.6, 'LGG'), (217.4, 'LLG'), (215.1, 'LLG'), (214.9, 'LLL'), (210, 'LLL')])
def test_band_far_bounds(header_y, expected):
    value = decide(pairs_of(tokens(header_y=header_y, month_height=10)))
    assert ''.join(value[rule][0] for rule in ('A', 'A_325', 'A_350')) == expected
    assert value['A_325+L'] == value['A_325'] and value['A_350+L'] == value['A_350']
    assert value['B'] == 'LEGACY'


def test_band_near_bound_excludes_month_row_neighbours():
    near = tokens(header_y=246, month_height=10)  # 0.4H above the first-month centre.
    assert {decide(pairs_of(near))[rule] for rule in ('A', 'A_325', 'A_350')} == {'LEGACY'}


@pytest.mark.parametrize('text,expected', [
    ('가입구분', True), ('[가입구분]', True), ('가입구분:', True), ('가입 구분', True), ('(가입·구분)', True),
    ('가입자구분', False), ('가입구븐', False), ('구분', False), ('직장가입자', False)])
def test_legacy_marker_normalization(text, expected):
    words = tokens()
    if text == '가입 구분':
        words += [word('가입', 500, 100, width=40), word('구분', 545, 100, width=40)]
    else:
        words += [word(text, 500, 100)]
    pairs = pairs_of(words)
    assert shadow.legacy_marker(pairs) is expected
    assert shadow.government(pairs, 'OLD_CURRENT') is True
    assert decide(pairs)['L'] == ('LEGACY' if expected else 'GOVERNMENT')


def test_marker_on_another_line_is_not_joined():
    words = tokens() + [word('가입', 500, 100, width=40), word('구분', 500, 140, width=40)]
    assert shadow.legacy_marker(pairs_of(words)) is False


def test_marker_overrides_band_rules_only_when_present():
    words = tokens(header_y=225, month_height=10)  # 2.5H: every band rule says GOVERNMENT.
    plain, marked = decide(pairs_of(words)), decide(pairs_of(words + [word('가입구분', 500, 100)]))
    assert {plain[rule] for rule in ('A', 'A_325', 'A_350', 'A_325+L', 'A_350+L')} == {'GOVERNMENT'}
    assert {marked[rule] for rule in ('L', 'A_325+L', 'A_350+L')} == {'LEGACY'}
    assert {marked[rule] for rule in ('A', 'A_325', 'A_350')} == {'GOVERNMENT'}


@pytest.mark.parametrize('name', ['가상', '가상인명'])
@pytest.mark.parametrize('scale,jitter,skew', [(.7, 0, 0), (1, 3, 14), (1.7, 4, -12)])
@pytest.mark.parametrize('trailing_blank', [False, True])
def test_government_geometry_variants_have_no_marker_and_keep_l(name, scale, jitter, skew, trailing_blank):
    from engine_v2.tests import p2_payment_samples as sample
    cells, size = sample.payment(name=name, corrected=True, trailing_blank=trailing_blank)
    pairs = [sample.page(cells, size=size, scale=scale, jitter=jitter, skew=skew)]
    value = decide(pairs)
    assert shadow.legacy_marker(pairs) is False
    assert gov.recognizes(pairs) is True
    assert value['CURRENT'] == value['L'] == 'GOVERNMENT'


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('labels', [{'고지금액', '납부금액'}, {'보수외', '소득월액'}])
def test_split_government_headers_have_no_marker_and_keep_l(vertical, labels):
    from engine_v2.tests import p2_shape3_samples as sample
    from engine_v2.tests.p2_form_samples import page
    from engine_v2.tests.test_p2_payment_headers import split_words
    cells, size = sample.document('payment')
    pairs = [page(split_words(cells, labels, vertical=vertical), size=size)]
    assert shadow.legacy_marker(pairs) is False
    assert decide(pairs)['L'] == 'GOVERNMENT'


def test_legacy_reader_fixture_carries_marker():
    from engine_v2.tests.test_nhis_extractors import payment_pages
    pages = payment_pages()
    assert shadow.legacy_marker(pages) is True
    assert set(decide(pages).values()) == {'LEGACY'}


def test_structure_rule_needs_gates_and_complete_table():
    from engine_v2.tests import p2_payment_samples as sample
    cells, size = sample.payment()
    pairs = [sample.page(cells, size=size)]
    assert shadow.structure(pairs) is True
    no_gate = [cell for cell in cells if cell[4] not in ('문서확인번호:0000-0000-0000-00000', '납부자번호')]
    assert shadow.structure([sample.page(no_gate, size=size)]) is False
    no_december = [cell for cell in cells if cell[4] != '12월']
    assert shadow.structure([sample.page(no_december, size=size)]) is False
    assert shadow.structure(pairs_of(tokens())) is False


@pytest.mark.parametrize('value,label', [
    (0.0, '0.000-2.000'), (1.999, '0.000-2.000'), (2.0, '2.000-2.125'), (2.124, '2.000-2.125'),
    (2.125, '2.125-2.250'), (3.25, '3.250-3.375'), (3.999, '3.875-4.000'), (4.0, '4.000-4.500'),
    (4.5, '4.500-5.000'), (5.999, '5.500-6.000'), (6.0, '6.000+'), (40.0, '6.000+'), (None, 'NA')])
def test_distance_bins(value, label):
    assert shadow.distance_bin(value) == label


def test_distance_bin_names_are_closed():
    assert len(shadow.DISTANCE_BINS) == 23 and len(set(shadow.DISTANCE_BINS)) == 23
    assert shadow.DISTANCE_BINS[:3] == ('0.000-2.000', '2.000-2.125', '2.125-2.250')
    assert shadow.DISTANCE_BINS[-7:] == ('3.875-4.000', '4.000-4.500', '4.500-5.000', '5.000-5.500',
                                         '5.500-6.000', '6.000+', 'NA')
    for bad in (-.1, float('nan'), 3):
        with pytest.raises(shadow.ShadowRouteError):
            shadow.distance_bin(bad)


def test_third_nearest_distance_uses_words_above_the_first_month_only():
    words = [*tokens(copies=0, month_height=10),
             word('보수외', 50, 215), word('보수외', 140, 225), word('보수외', 230, 222), word('보수외', 320, 180),
             word('보수외', 410, 300), word('소득월액', 50, 230), word('소득월액', 140, 231)]
    value = shadow.third_distances(pairs_of(words))
    assert value['BOSUOE'] == pytest.approx(3.5)
    assert value['INCOME'] is None
    measures = shadow.candidates(pairs_of(words), 'LEGACY')['measures']
    assert measures == {'BOSUOE': '3.500-3.625', 'INCOME': 'NA', 'MARKER': 'X'}


def test_combined_phrase_counts_for_both_measures_and_missing_month_is_na():
    measures = shadow.candidates(pairs_of(tokens(copies=4, header_y=220, month_height=10)), 'LEGACY')['measures']
    assert measures['BOSUOE'] == measures['INCOME'] == '3.000-3.125'
    no_month = [item for item in tokens() if item.text != '1월']
    assert shadow.third_distances(pairs_of(no_month)) == {'BOSUOE': None, 'INCOME': None}


def test_path_without_payment_dispatch_keeps_actual_branch_and_na_measures():
    def other(page, words, engine):
        return None, {}, 'OTHER'
    found, extra = [], []
    route.inspect_extraction(canvas(), tokens(), 'own', other, found, extra)
    assert found == [dict.fromkeys(shadow.RULES, 'OTHER')]
    assert extra == [dict(rules=dict.fromkeys(shadow.CANDIDATES, 'OTHER'),
                          measures={'BOSUOE': 'NA', 'INCOME': 'NA', 'MARKER': 'NA'})]


def test_candidate_failure_is_a_fixed_error_and_keeps_existing_shadow(monkeypatch):
    def fail(*_):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(shadow, 'structure', fail)
    form, value = observe(canvas(), tokens(), 'own')
    assert value == {'CURRENT': form, 'OLD_CURRENT': form, 'A': 'LEGACY', 'S': 'LEGACY'}
    _, combined, measures = capture(canvas(), tokens(), 'own')
    assert combined['B'] == 'ERROR' and combined['L'] == form
    assert measures['MARKER'] == 'X'
    monkeypatch.setattr(shadow, 'candidates', fail)
    found, extra = [], []
    route.inspect_extraction(canvas(), tokens(), 'own', evidence.extract_with_form, found, extra)
    assert extra == [shadow.failed_candidates()] and SENTINEL not in json.dumps(extra)


def test_end_to_end_candidate_rows_distribution_and_marker(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    assert invoke(root, out) == 0
    summary = json.loads((out/'summary.json').read_text())
    value = summary['shadow_candidates']
    engines = ('text_layer', 'own', 'applevision')
    routes = {(r['rule'], r['engine'], r['form']): r['pages'] for r in value['routes'] if r['pages']}
    assert routes == {(rule, engine, 'GOVERNMENT' if rule == 'L' else 'LEGACY'): 1
                      for rule in shadow.CANDIDATES for engine in engines}
    distances = {(r['engine'], r['measure'], r['bin']): r['pages'] for r in value['distances'] if r['pages']}
    assert distances == {(engine, measure, '5.500-6.000'): 1 for engine in engines for measure in shadow.MEASURES}
    assert {(r['engine'], r['marker']): r['pages'] for r in value['markers'] if r['pages']} == {
        (engine, 'X'): 1 for engine in engines}
    brief = (out/'summary_brief.txt').read_text()
    for line in ('CANDIDATE_RULES A_325 A_350 B L A_325+L A_350+L\n', 'CANDIDATE_ALIAS A_300 A\n',
                 'CANDIDATE_ALIAS CURRENT+L L\n', 'CANDIDATE_ROUTE L own GOVERNMENT 1\n',
                 'CANDIDATE_ROUTE A_325+L own LEGACY 1\n', 'CANDIDATE_ROUTE B own GOVERNMENT 0\n',
                 'CANDIDATE_CROSS L own GOVERNMENT GOVERNMENT 1\n', 'DIST3 own BOSUOE 5.500-6.000 1\n',
                 'DIST3 text_layer INCOME 5.500-6.000 1\n', 'MARKER own X 1\n', 'MARKER own O 0\n',
                 'SHADOW_ROUTE CURRENT own GOVERNMENT 1\n'):
        assert line in brief
    for absent in ('CANDIDATE_ROUTE B own ERROR', 'DIST3 own BOSUOE NA', 'MARKER own NA', 'CANDIDATE_CROSS B own GOVERNMENT'):
        assert absent not in brief
    text = (out/'summary.txt').read_text()
    assert 'DIST3 own BOSUOE NA 0\n' in text and 'MARKER own NA 0\n' in text
    assert 'CANDIDATE_ROUTE B own ERROR 0\n' in text
    assert text.index('SHADOW_CHECK') < text.index('CANDIDATE_RULES')
    families = ('CANDIDATE_RULES', 'CANDIDATE_ALIAS', 'CANDIDATE_ROUTE', 'CANDIDATE_CROSS', 'DIST3', 'MARKER')
    new = [line for line in brief.splitlines() if line.split()[0] in families]
    tokens_allowed = {*shadow.RULES, *shadow.CANDIDATES, *shadow.MARKER_RULES, *dict(shadow.ALIASES), *shadow.BRANCHES,
                      *shadow.MEASURES, *shadow.DISTANCE_BINS, *shadow.MARKERS, *engines}
    assert new and all(token.isdigit() or token in tokens_allowed for line in new for token in line.split()[1:])
    assert_private_output(out, capfd)


def test_candidate_error_sets_failure_exit(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    def fail(*_):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(shadow, 'structure', fail)
    assert invoke(root, out) == 1
    value = json.loads((out/'summary.json').read_text())['shadow_candidates']
    assert shadow.candidate_failures(value) == 3
    assert 'CANDIDATE_ROUTE B own ERROR 1\n' in (out/'summary_brief.txt').read_text()
    assert_private_output(out, capfd)


def observation(document, engine, form='LEGACY', **rules):
    return dict(document=document, page=1, engine=engine, form=form,
                rules={**dict.fromkeys(shadow.CANDIDATES, 'LEGACY'), **rules},
                measures={'BOSUOE': 'NA', 'INCOME': '2.000-2.125', 'MARKER': 'O'})


def test_candidate_cross_and_distributions_count_each_page_once():
    meta = {'engines': ['own']}
    observations = [observation(1, 'text_layer'), observation(1, 'own', L='GOVERNMENT'),
                    observation(2, 'text_layer'), observation(2, 'own'), observation(3, 'own')]
    value = shadow.build_candidate_summary(meta, observations)
    shadow.validate_candidate_summary(value)
    cross = {(r['rule'], r['reference_form'], r['form']): r['pages'] for r in value['cross'] if r['pages']}
    assert cross[('L', 'LEGACY', 'GOVERNMENT')] == 1 and cross[('L', 'LEGACY', 'LEGACY')] == 1
    assert cross[('B', 'LEGACY', 'LEGACY')] == 2
    distances = {(r['engine'], r['measure'], r['bin']): r['pages'] for r in value['distances'] if r['pages']}
    assert distances == {('text_layer', 'BOSUOE', 'NA'): 2, ('text_layer', 'INCOME', '2.000-2.125'): 2,
                         ('own', 'BOSUOE', 'NA'): 3, ('own', 'INCOME', '2.000-2.125'): 3}
    assert {(r['engine'], r['marker']): r['pages'] for r in value['markers'] if r['pages']} == {
        ('text_layer', 'O'): 2, ('own', 'O'): 3}
    assert len(value['distances']) == 2 * 2 * len(shadow.DISTANCE_BINS)
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_candidate_summary(meta, observations + [observation(3, 'own')])


@pytest.mark.parametrize('bad', [
    dict(rules={'L': 'LEGACY'}), dict(rules={**dict.fromkeys(shadow.CANDIDATES, 'LEGACY'), 'L': SENTINEL}),
    dict(measures={'BOSUOE': SENTINEL, 'INCOME': 'NA', 'MARKER': 'O'}),
    dict(measures={'BOSUOE': 'NA', 'INCOME': 'NA', 'MARKER': SENTINEL}),
    dict(measures={'BOSUOE': 'NA', 'INCOME': 'NA'}), dict(form=SENTINEL), dict(engine=SENTINEL),
    dict(page=0), dict(extra=SENTINEL)])
def test_candidate_observation_is_closed(bad):
    item = {**observation(1, 'own'), **bad}
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_candidate_summary({'engines': ['own']}, [item])


@pytest.mark.parametrize('mutation', ['unknown-key', 'unknown-rule', 'alias', 'unknown-bin', 'unknown-marker',
                                      'bool-count', 'float-count', 'engine'])
def test_candidate_summary_closed_schema(mutation):
    meta = {'engines': ['own'], 'fields': []}
    rows = [tool.row(1, 1, 'NHIS_PAYMENT', 'LEGACY')]
    candidates = [observation(1, 'text_layer'), observation(1, 'own')]
    value = tool.build_summary(meta, rows, dict.fromkeys(tool.COUNTERS, 0), (), (), candidates)
    tool.validate_summary(deepcopy(value), meta, rows, (), (), candidates)
    target = value['shadow_candidates']
    if mutation == 'unknown-key':
        target[SENTINEL] = 0
    elif mutation == 'unknown-rule':
        target['routes'][0]['rule'] = SENTINEL
    elif mutation == 'alias':
        target['aliases'][0]['rule'] = SENTINEL
    elif mutation == 'unknown-bin':
        target['distances'][0]['bin'] = SENTINEL
    elif mutation == 'unknown-marker':
        target['markers'][0]['marker'] = SENTINEL
    elif mutation == 'bool-count':
        target['markers'][0]['pages'] = True
    elif mutation == 'float-count':
        target['distances'][0]['pages'] = 0.0
    else:
        target['routes'][0]['engine'] = SENTINEL
    with pytest.raises((tool.DiagnosticError, shadow.ShadowRouteError)):
        tool.validate_summary(value, meta, rows, (), (), candidates)
    with pytest.raises(shadow.ShadowRouteError):
        shadow.validate_candidate_summary(target)
