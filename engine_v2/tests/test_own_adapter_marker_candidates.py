"""Legacy-marker candidates taken from the legacy reader's own clues (diagnostic only)."""
from copy import deepcopy
import json

import pytest

from engine_v2.extractors import nhis_payment_gov as gov
from engine_v2.tools import own_adapter_diag as tool
from engine_v2.tools import own_adapter_diag_evidence as evidence
from engine_v2.tools import own_adapter_route_diag as route
from engine_v2.tools import own_adapter_shadow_route as shadow
from engine_v2.tools.ocr_baseline_fields import prepare_pairs
from engine_v2.tests.test_own_adapter_route_diag import (
    SENTINEL, assert_private_output, canvas, install_payment, invoke, locations, tokens, word)  # noqa: F401
from engine_v2.tests.test_own_adapter_shadow_route import REPRODUCTION, grid_pdf, ocr_case, text_layer

ENGINES = ('text_layer', 'own', 'applevision')


def capture(page, words, engine):
    markers = []
    extracted, _ = route.inspect_extraction(page, words, engine, evidence.extract_with_form, None, None, markers)
    assert len(markers) == 1
    return extracted[2], markers[0]


def pairs_of(words):
    return prepare_pairs(canvas(), words, 'own')


def states(value):
    return ''.join(value['markers'][name] for name in shadow.MARKER_CANDIDATES)


def code(value):
    return ''.join(value['rules'][rule][0] for rule in shadow.MARKER_RULES)


def found(words):
    return {name for name, present in shadow.legacy_markers(pairs_of(words)).items() if present}


def rows(first_boxes, *, top=400, step=40):
    return [word(text, 50, top + index * step) for index, text in enumerate(first_boxes)]


# Marker order: RRN_LABEL MEMBER_CLASS_LABEL LEGACY_ALIAS_LABEL YEAR_MONTH_ROWS MONTH_TABLE_ROWS MEMBER_TYPE_VALUE.
# Rule order: L_<marker>, L_<marker>+A_325 for each marker (G = GOVERNMENT, L = LEGACY).


def test_marker_names_kinds_and_rules_are_closed():
    assert shadow.MARKER_CANDIDATES == ('RRN_LABEL', 'MEMBER_CLASS_LABEL', 'LEGACY_ALIAS_LABEL',
                                        'YEAR_MONTH_ROWS', 'MONTH_TABLE_ROWS', 'MEMBER_TYPE_VALUE')
    assert [kind for _, kind in shadow.MARKER_KINDS] == ['LABEL', 'LABEL', 'LABEL', 'STRUCTURE', 'STRUCTURE', 'VALUE']
    assert shadow.MARKER_RULES[:4] == ('L_RRN_LABEL', 'L_RRN_LABEL+A_325',
                                       'L_MEMBER_CLASS_LABEL', 'L_MEMBER_CLASS_LABEL+A_325')
    assert len(shadow.MARKER_RULES) == len(set(shadow.MARKER_RULES)) == 12
    assert not set(shadow.MARKER_RULES) & {*shadow.RULES, *shadow.CANDIDATES}
    with pytest.raises(shadow.ShadowRouteError):
        shadow.marker_government(pairs_of(tokens()), 'L')


@pytest.mark.parametrize('name,texts', [
    ('RRN_LABEL', ['주민등록번호']), ('RRN_LABEL', ['(주민 등록번호)']), ('RRN_LABEL', ['주민등록', '번호:']),
    ('MEMBER_CLASS_LABEL', ['가입구분']), ('MEMBER_CLASS_LABEL', ['가입자 구분:']), ('MEMBER_CLASS_LABEL', ['[가입자', '구분]']),
    ('LEGACY_ALIAS_LABEL', ['고지보험료']), ('LEGACY_ALIAS_LABEL', ['납부 보험료']), ('LEGACY_ALIAS_LABEL', ['실납부']),
    ('LEGACY_ALIAS_LABEL', ['출력일:']), ('LEGACY_ALIAS_LABEL', ['발행일']),
    ('MEMBER_TYPE_VALUE', ['직장가입자']), ('MEMBER_TYPE_VALUE', ['지역 가입자']), ('MEMBER_TYPE_VALUE', ['직장·가입'])])
def test_phrase_markers_on_one_line_after_noise_removal(name, texts):
    words = tokens() + [word(text, 500 + index * 90, 140) for index, text in enumerate(texts)]
    assert found(words) == {name}


@pytest.mark.parametrize('texts', [['주민등록번효'], ['가입구븐'], ['고지보험르'], ['직장가잎자'], ['주민-등록번호']])
def test_phrase_markers_apply_no_misread_correction(texts):
    assert found(tokens() + [word(text, 500, 140) for text in texts]) == set()


def test_phrase_markers_are_not_joined_across_lines():
    words = tokens() + [word('주민등록', 500, 140), word('번호', 500, 170),
                        word('가입자', 600, 140), word('구분', 600, 170), word('직장', 700, 140), word('가입자', 700, 170)]
    assert found(words) == set()


def test_government_reader_labels_are_not_markers():
    words = tokens() + [word(text, 500, 130 + index * 25) for index, text in enumerate(
        ('가입자성명', '생년월일', '발급일', '발급일자', '납부총액', '고지금액', '납부금액', '사업장명칭', '월별', '합계'))]
    assert found(words) == set()


@pytest.mark.parametrize('boxes,expected', [
    (['2025.01', '2025-02', '2025년 3월'], True), (['202501', '2025.02.', '2025/03'], True), (['202501', '202502.', '2025/03'], False),
    (['2025.01', '2025.02'], False), (['1월', '2월', '3월'], False),
    (['2025.01.15', '2025.02.15', '2025.03.15'], False), (['2025년1월~2025년3월', '2025.02', '2025.03'], False)])
def test_year_month_rows_need_three_leftmost_year_month_boxes(boxes, expected):
    assert ('YEAR_MONTH_ROWS' in found(tokens(copies=0) + rows(boxes))) is expected


def test_year_month_rows_ignore_year_months_that_are_not_the_leftmost_box():
    words = tokens(copies=0) + [item for index in range(3) for item in
                                (word('합', 40, 400 + index * 40, width=5), word(f'2025.0{index + 1}', 100, 400 + index * 40))]
    assert 'YEAR_MONTH_ROWS' not in found(words)


def table(labels, months, *, end=None):
    header = [word(label, 50 + index * 120, 360) for index, label in enumerate(labels)]
    body = [word(text, 50 + 120 * column, 400 + index * 40)
            for index, month in enumerate(months) for column, text in enumerate((*month.split('|'),))]
    closing = [word(end, 50, 400 + len(months) * 40)] if end else []
    return [word('건강보험료납부확인서', 50, 20, width=180), *header, *body, *closing]


@pytest.mark.parametrize('labels,months,expected', [
    (('년월', '고지금액'), ('2025.01|1000', '2025.02|1000', '2025.03|1000'), True),
    (('납부년월', '고지금액'), ('비고 2025-01|1000', '비고 2025-02|1000', '비고 2025-03|1000'), True),
    (('년월', '고지금액'), ('2025.01|1000', '2025.02|1000'), False),
    (('월별', '고지금액'), ('1월|1000', '2월|1000', '3월|1000'), False),
    (('구분', '고지금액'), ('2025.01|1000', '2025.02|1000', '2025.03|1000'), False)])
def test_month_table_rows_follow_the_legacy_month_header(labels, months, expected):
    assert ('MONTH_TABLE_ROWS' in found(table(labels, months))) is expected


@pytest.mark.parametrize('end', ['합계', '납부총액', '위와 같이 확인합니다', '국민건강보험공단'])
def test_month_table_rows_stop_at_the_closing_line(end):
    words = table(('년월', '고지금액'), ('2025.01|1000', '2025.02|1000'), end=end)
    words.append(word('2025.03', 300, 400 + 3 * 40 + 40))
    assert 'MONTH_TABLE_ROWS' not in found(words)


def test_marker_rules_return_legacy_only_when_their_marker_is_present():
    plain = pairs_of(tokens(header_y=225, month_height=10))  # 2.5H: CURRENT and A_325 both say GOVERNMENT.
    assert code(shadow.marker_candidates(plain, 'GOVERNMENT')) == 'G' * 12
    marked = pairs_of(tokens(header_y=225, month_height=10) + [word('주민등록번호', 500, 140)])
    value = shadow.marker_candidates(marked, 'GOVERNMENT')
    assert states(value) == 'OXXXXX'
    assert code(value) == 'LL' + 'G' * 10
    far = pairs_of(tokens())  # Header 5.5H above the month centre: CURRENT GOVERNMENT, A_325 LEGACY.
    assert code(shadow.marker_candidates(far, 'GOVERNMENT')) == 'GL' * 6
    assert shadow.government(far, 'CURRENT') is True and shadow.government(far, 'A_325') is False


@pytest.mark.parametrize('name', ['가상', '가상인명'])
@pytest.mark.parametrize('scale,jitter,skew', [(.7, 0, 0), (1, 3, 14), (1.7, 4, -12)])
@pytest.mark.parametrize('trailing_blank', [False, True])
def test_government_geometry_variants_have_no_marker(name, scale, jitter, skew, trailing_blank):
    from engine_v2.tests import p2_payment_samples as sample
    cells, size = sample.payment(name=name, corrected=True, trailing_blank=trailing_blank)
    pairs = [sample.page(cells, size=size, scale=scale, jitter=jitter, skew=skew)]
    value = shadow.marker_candidates(pairs, 'GOVERNMENT')
    assert gov.recognizes(pairs) is True
    assert states(value) == 'XXXXXX'
    assert all(value['rules'][rule] == 'GOVERNMENT' for rule in shadow.MARKER_RULES if '+' not in rule)


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('labels', [{'고지금액', '납부금액'}, {'보수외', '소득월액'}])
def test_split_government_headers_have_no_marker(vertical, labels):
    from engine_v2.tests import p2_shape3_samples as sample
    from engine_v2.tests.p2_form_samples import page
    from engine_v2.tests.test_p2_payment_headers import split_words
    cells, size = sample.document('payment')
    pairs = [page(split_words(cells, labels, vertical=vertical), size=size)]
    value = shadow.marker_candidates(pairs, 'GOVERNMENT')
    assert states(value) == 'XXXXXX'
    assert all(value['rules'][rule] == 'GOVERNMENT' for rule in shadow.MARKER_RULES if '+' not in rule)


def test_legacy_reader_fixture_markers():
    from engine_v2.tests.test_nhis_extractors import payment_pages
    value = shadow.marker_candidates(payment_pages(), 'LEGACY')
    assert states(value) == 'XOXOOO'
    assert code(value) == 'L' * 12


@pytest.mark.parametrize('font', (8, 10, 12))
@pytest.mark.parametrize('gap', (3.0, 3.5, 4.0, 4.5))
def test_render_grid_carries_only_the_member_type_value(font, gap):
    form, value = capture(*text_layer(grid_pdf(font, gap)), 'text_layer')
    assert states(value) == 'XXXXXO'
    assert code(value) == ('GGGGGGGGGGLL' if gap < 4.5 else 'L' * 12)
    # The member-type value now routes the grid to the legacy reader at every gap.
    assert form == value['rules']['L_MEMBER_TYPE_VALUE'] == 'LEGACY'


REPRODUCED = {('own', 4): 'GGGGGGGGGGLL', ('own', 8): 'GLGLGLGLGLLL', ('own', 12): 'GLGLGLGLGLLL',
              ('applevision', 4): 'L' * 12, ('applevision', 8): 'L' * 12, ('applevision', 12): 'L' * 12}


@pytest.mark.parametrize('case', sorted(REPRODUCTION))
@pytest.mark.parametrize('engine', ('own', 'applevision'))
def test_actual_ocr_reproductions_under_marker_rules(case, engine):
    form, value = capture(*ocr_case(case, engine), engine)
    assert states(value) == 'XXXXXO'
    assert code(value) == REPRODUCED[(engine, case)]
    assert form == value['rules']['L_MEMBER_TYPE_VALUE'] == 'LEGACY'


def test_path_without_payment_dispatch_keeps_actual_branch_and_na_markers():
    def other(page, words, engine):
        return None, {}, 'OTHER'
    markers = []
    route.inspect_extraction(canvas(), tokens(), 'own', other, None, None, markers)
    assert markers == [dict(rules=dict.fromkeys(shadow.MARKER_RULES, 'OTHER'),
                            markers=dict.fromkeys(shadow.MARKER_CANDIDATES, 'NA'))]


def test_marker_failure_is_a_fixed_error_and_keeps_earlier_records(monkeypatch):
    def fail(*_):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(shadow, 'legacy_markers', fail)
    found_shadow, extra, markers = [], [], []
    extracted, _ = route.inspect_extraction(canvas(), tokens(), 'own', evidence.extract_with_form,
                                            found_shadow, extra, markers)
    assert markers == [shadow.failed_marker_candidates()] and SENTINEL not in json.dumps(markers)
    assert found_shadow[0]['CURRENT'] == extracted[2] and extra[0]['rules']['L'] == extracted[2]
    monkeypatch.setattr(shadow, 'marker_candidates', fail)
    markers = []
    route.inspect_extraction(canvas(), tokens(), 'own', evidence.extract_with_form, None, None, markers)
    assert markers == [shadow.failed_marker_candidates()]


def test_end_to_end_marker_rows_and_lines(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    assert invoke(root, out) == 0
    summary = json.loads((out/'summary.json').read_text())
    value = summary['shadow_markers']
    routes = {(r['rule'], r['engine'], r['form']): r['pages'] for r in value['routes'] if r['pages']}
    assert routes == {(rule, engine, 'LEGACY' if rule.endswith('+A_325') else 'GOVERNMENT'): 1
                      for rule in shadow.MARKER_RULES for engine in ENGINES}
    assert {(r['marker'], r['engine'], r['state']): r['pages'] for r in value['states'] if r['pages']} == {
        (name, engine, 'X'): 1 for name in shadow.MARKER_CANDIDATES for engine in ENGINES}
    brief = (out/'summary_brief.txt').read_text()
    for line in ('MARKER_CAND_RULES ' + ' '.join(shadow.MARKER_RULES) + '\n',
                 'MARKER_CAND_KIND RRN_LABEL LABEL\n', 'MARKER_CAND_KIND MEMBER_TYPE_VALUE VALUE\n',
                 'MARKER_CAND RRN_LABEL own X 1\n', 'MARKER_CAND RRN_LABEL own O 0\n',
                 'MARKER_CAND MONTH_TABLE_ROWS applevision X 1\n',
                 'CANDIDATE_ROUTE L_RRN_LABEL own GOVERNMENT 1\n', 'CANDIDATE_ROUTE L_RRN_LABEL+A_325 own LEGACY 1\n',
                 'CANDIDATE_ROUTE L_MEMBER_TYPE_VALUE text_layer LEGACY 0\n',
                 'CANDIDATE_CROSS L_RRN_LABEL own GOVERNMENT GOVERNMENT 1\n',
                 'CANDIDATE_RULES A_325 A_350 B L A_325+L A_350+L\n', 'MARKER own X 1\n'):
        assert line in brief
    for absent in ('MARKER_CAND RRN_LABEL own NA', 'CANDIDATE_ROUTE L_RRN_LABEL own ERROR',
                   'CANDIDATE_CROSS L_RRN_LABEL own GOVERNMENT LEGACY'):
        assert absent not in brief
    text = (out/'summary.txt').read_text()
    assert 'MARKER_CAND RRN_LABEL own NA 0\n' in text and 'CANDIDATE_ROUTE L_RRN_LABEL own ERROR 0\n' in text
    for document in (text, brief):
        assert document.index('MARKER own X 1') < document.index('MARKER_CAND_RULES')
        assert document.index('MARKER_CAND_RULES') < document.index('CANDIDATE_ROUTE L_RRN_LABEL ')
    families = ('MARKER_CAND_RULES', 'MARKER_CAND_KIND', 'MARKER_CAND', 'CANDIDATE_ROUTE', 'CANDIDATE_CROSS')
    new = [line for line in brief.splitlines() if line.split()[0] in families]
    allowed = {*shadow.CANDIDATES, *shadow.MARKER_RULES, *shadow.MARKER_CANDIDATES, 'LABEL', 'STRUCTURE', 'VALUE',
               *shadow.BRANCHES, *shadow.MARKERS, *ENGINES}
    assert new and all(token.isdigit() or token in allowed for line in new for token in line.split()[1:])
    assert_private_output(out, capfd)


def test_marker_error_sets_failure_exit(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    def fail(*_):
        raise RuntimeError(SENTINEL)
    monkeypatch.setattr(shadow, 'legacy_markers', fail)
    assert invoke(root, out) == 1
    value = json.loads((out/'summary.json').read_text())['shadow_markers']
    assert shadow.marker_failures(value) == 3 * len(shadow.MARKER_RULES)
    brief = (out/'summary_brief.txt').read_text()
    assert 'CANDIDATE_ROUTE L_RRN_LABEL own ERROR 1\n' in brief and 'MARKER_CAND RRN_LABEL own NA 1\n' in brief
    assert 'CANDIDATE_ROUTE L own GOVERNMENT 1\n' in brief
    assert_private_output(out, capfd)


def observation(document, engine, form='LEGACY', markers=None, **rules):
    return dict(document=document, page=1, engine=engine, form=form,
                rules={**dict.fromkeys(shadow.MARKER_RULES, 'LEGACY'), **rules},
                markers={**dict.fromkeys(shadow.MARKER_CANDIDATES, 'X'), **(markers or {})})


def test_marker_cross_and_states_count_each_page_once():
    meta = {'engines': ['own']}
    observations = [observation(1, 'text_layer', markers={'RRN_LABEL': 'O'}),
                    observation(1, 'own', L_RRN_LABEL='GOVERNMENT'),
                    observation(2, 'text_layer'), observation(2, 'own', markers={'RRN_LABEL': 'O'}),
                    observation(3, 'own', markers={'RRN_LABEL': 'NA'})]
    value = shadow.build_marker_summary(meta, observations)
    shadow.validate_marker_summary(value)
    cross = {(r['rule'], r['reference_form'], r['form']): r['pages'] for r in value['cross'] if r['pages']}
    assert cross[('L_RRN_LABEL', 'LEGACY', 'GOVERNMENT')] == 1 and cross[('L_RRN_LABEL', 'LEGACY', 'LEGACY')] == 1
    assert cross[('L_MEMBER_TYPE_VALUE', 'LEGACY', 'LEGACY')] == 2
    found_states = {(r['engine'], r['state']): r['pages'] for r in value['states']
                    if r['pages'] and r['marker'] == 'RRN_LABEL'}
    assert found_states == {('text_layer', 'O'): 1, ('text_layer', 'X'): 1, ('own', 'O'): 1, ('own', 'X'): 1,
                            ('own', 'NA'): 1}
    assert len(value['states']) == len(shadow.MARKER_CANDIDATES) * 2 * len(shadow.MARKERS)
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_marker_summary(meta, observations + [observation(3, 'own')])


@pytest.mark.parametrize('bad', [
    dict(rules={'L_RRN_LABEL': 'LEGACY'}), dict(rules={**dict.fromkeys(shadow.MARKER_RULES, 'LEGACY'), 'L': 'LEGACY'}),
    dict(rules={**dict.fromkeys(shadow.MARKER_RULES, 'LEGACY'), 'L_RRN_LABEL': SENTINEL}),
    dict(markers={**dict.fromkeys(shadow.MARKER_CANDIDATES, 'X'), 'RRN_LABEL': SENTINEL}),
    dict(markers={'RRN_LABEL': 'O'}), dict(form=SENTINEL), dict(engine=SENTINEL), dict(page=0), dict(extra=SENTINEL)])
def test_marker_observation_is_closed(bad):
    item = {**observation(1, 'own'), **bad}
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_marker_summary({'engines': ['own']}, [item])


@pytest.mark.parametrize('mutation', ['unknown-key', 'unknown-rule', 'kind', 'unknown-marker', 'unknown-state',
                                      'bool-count', 'float-count', 'engine'])
def test_marker_summary_closed_schema(mutation):
    meta = {'engines': ['own'], 'fields': []}
    rows_ = [tool.row(1, 1, 'NHIS_PAYMENT', 'LEGACY')]
    markers = [observation(1, 'text_layer'), observation(1, 'own')]
    value = tool.build_summary(meta, rows_, dict.fromkeys(tool.COUNTERS, 0), (), (), (), markers)
    tool.validate_summary(deepcopy(value), meta, rows_, (), (), (), markers)
    target = value['shadow_markers']
    if mutation == 'unknown-key':
        target[SENTINEL] = 0
    elif mutation == 'unknown-rule':
        target['routes'][0]['rule'] = SENTINEL
    elif mutation == 'kind':
        target['markers'][0]['kind'] = 'VALUE'
    elif mutation == 'unknown-marker':
        target['states'][0]['marker'] = SENTINEL
    elif mutation == 'unknown-state':
        target['states'][0]['state'] = SENTINEL
    elif mutation == 'bool-count':
        target['routes'][0]['pages'] = True
    elif mutation == 'float-count':
        target['states'][0]['pages'] = 1.0
    else:
        target['cross'][0]['engine'] = SENTINEL
    with pytest.raises((tool.DiagnosticError, shadow.ShadowRouteError)):
        tool.validate_summary(value, meta, rows_, (), (), (), markers)
    with pytest.raises(shadow.ShadowRouteError):
        shadow.validate_marker_summary(target)


def test_summary_requires_the_marker_section():
    meta = {'engines': ['own'], 'fields': []}
    rows_ = [tool.row(1, 1, 'NHIS_PAYMENT', 'LEGACY')]
    value = tool.build_summary(meta, rows_, dict.fromkeys(tool.COUNTERS, 0))
    assert value['shadow_markers']['rules'] == list(shadow.MARKER_RULES)
    del value['shadow_markers']
    with pytest.raises((tool.DiagnosticError, shadow.ShadowRouteError)):
        tool.validate_summary(value, meta, rows_)
