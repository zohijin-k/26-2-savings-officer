"""Shadow routing rules CURRENT, OLD_CURRENT, A and S: authored layouts, OCR reproductions and value-free aggregates."""
from copy import deepcopy
import json
from pathlib import Path

import pymupdf
import pytest

from engine_v2.extractors import nhis_payment_gov as gov
from engine_v2.pipeline.ocr import OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tools import own_adapter_diag as tool
from engine_v2.tools import own_adapter_diag_evidence as evidence
from engine_v2.tools import own_adapter_route_diag as route
from engine_v2.tools import own_adapter_shadow_route as shadow
from engine_v2.tools import ocr_baseline_runtime as runtime
from engine_v2.tools.documentai_synth import Source, pdf_bytes
from engine_v2.tools.ocr_baseline_fields import prepare_pairs
from engine_v2.tests.test_own_adapter_route_diag import (
    SENTINEL, assert_private_output, canvas, install_payment, invoke, locations, tokens)  # noqa: F401

FIXTURE = Path(__file__).parent/'fixtures'/'payment_route_shadow'/'reproduction_ocr.json'
REPRODUCTION = {4: 8, 8: 10, 12: 12}  # case -> font size; gap multiplier 4.5.


def grid_pdf(font, gap):
    """Legacy three-month table with fictitious repeated component phrases above its header row."""
    month_y = 400
    cells = [(140, 60, '건강보험료납부확인서', font * 1.3), (50, 110, '성명', font), (150, 110, '가상시험', font),
             (320, 110, '생년월일', font), (420, 110, '1990.01.01', font), (50, 160, '사업장명칭', font),
             (175, 160, '가상연구사업장', font), (330, 160, '납부자번호', font), (430, 160, '00000000000', font),
             (50, 210, '직장가입자', font), (150, 260, '2025년1월~2025년3월납부내역', font)]
    cells.extend((50 + i * 135, month_y - gap * font, '보수외소득월액(건강)', font * .7) for i in range(4))
    cells.extend((x, month_y - font * 1.6, text, font)
                 for x, text in ((50, '월별'), (160, '건강보험료'), (300, '장기요양보험료'), (450, '납부금액')))
    for month in (1, 2, 3):
        y = month_y + (month - 1) * 35
        cells.extend((x, y, text, font) for x, text in
                     ((50, f'{month}월'), (160, '10000'), (300, '1000'), (450, '11000')))
    cells.extend([(50, 720, '발급일', font), (160, 720, '2026.11.10', font)])
    return pdf_bytes(Source('nhis_payment', [(cells, (595, 842))], {}, {}))


def text_layer(data):
    with pymupdf.open(stream=data, filetype='pdf') as document:
        return runtime.reference_page(document[0], 0)


def ocr_case(case, engine):
    entry = json.loads(FIXTURE.read_text())['cases'][str(case)]
    page = PageImage(0, PageSource[entry['source']], tuple(entry['page_size_pt']),
                     pixel_size=tuple(entry['pixel_size']), dpi=entry['dpi'])
    return page, [OcrWord(text, conf, tuple(box)) for text, conf, box in entry[engine]]


def observe(page, words, engine):
    found = []
    extracted, _ = route.inspect_extraction(page, words, engine, evidence.extract_with_form, found)
    assert len(found) == 1
    return extracted[2], found[0]


def rules(pairs):
    return {rule: 'GOVERNMENT' if shadow.government(pairs, rule) else 'LEGACY' for rule in shadow.RULES}


@pytest.mark.parametrize('font', (8, 10, 12))
@pytest.mark.parametrize('gap', (3.0, 3.5, 4.0, 4.5))
def test_render_grid_text_layer_routes_legacy_only_under_structure_rule(font, gap):
    # The authored grid carries 직장가입자, so the operating route is LEGACY at every gap;
    # OLD_CURRENT keeps the earlier band decision.
    form, value = observe(*text_layer(grid_pdf(font, gap)), 'text_layer')
    assert value['CURRENT'] == form == 'LEGACY'
    assert value['OLD_CURRENT'] == ('LEGACY' if gap == 4.5 else 'GOVERNMENT')
    assert value['A'] == value['OLD_CURRENT']
    assert value['S'] == 'LEGACY'


@pytest.mark.parametrize('case', sorted(REPRODUCTION))
@pytest.mark.parametrize('engine,old', [('own', 'GOVERNMENT'), ('applevision', 'LEGACY')])
def test_actual_ocr_reproductions(case, engine, old):
    form, value = observe(*ocr_case(case, engine), engine)
    assert form == value['CURRENT'] == 'LEGACY'
    assert value['OLD_CURRENT'] == old
    assert value['A'] == value['S'] == 'LEGACY'


@pytest.mark.parametrize('name', ['가상', '가상인', '가상인명'])
@pytest.mark.parametrize('scale,jitter,skew', [(.7, 0, 0), (1, 3, 14), (1.7, 4, -12)])
@pytest.mark.parametrize('trailing_blank', [False, True])
def test_government_geometry_variants_stay_government_under_current_and_structure(name, scale, jitter, skew, trailing_blank):
    from engine_v2.tests import p2_payment_samples as sample
    cells, size = sample.payment(name=name, corrected=True, trailing_blank=trailing_blank)
    pairs = [sample.page(cells, size=size, scale=scale, jitter=jitter, skew=skew)]
    value = rules(pairs)
    assert gov.recognizes(pairs) is True
    assert value['CURRENT'] == value['S'] == 'GOVERNMENT'


@pytest.mark.parametrize('vertical', [False, True])
@pytest.mark.parametrize('labels', [
    {'고지금액', '납부금액'}, {'건강', '장기요양', '보험료'}, {'보수외', '소득월액'},
    {'고지금액', '납부금액', '건강', '장기요양', '보험료', '보수외', '소득월액'},
])
def test_split_government_headers_stay_government_under_current_and_structure(vertical, labels):
    from engine_v2.tests import p2_shape3_samples as sample
    from engine_v2.tests.p2_form_samples import page
    from engine_v2.tests.test_p2_payment_headers import split_words
    cells, size = sample.document('payment')
    pairs = [page(split_words(cells, labels, vertical=vertical), size=size)]
    value = rules(pairs)
    assert gov.recognizes(pairs) is True
    assert value['CURRENT'] == value['S'] == 'GOVERNMENT'


def test_legacy_table_with_government_identity_stays_legacy_under_every_rule():
    from engine_v2.tests.test_nhis_extractors import payment_pages, wd
    pages = payment_pages()
    pages[0][1].words.extend([wd(10, 20, '문서확인번호:0000-0000-0000-00000', 60),
                              wd(10, 22, '사업장명칭'), wd(30, 22, '가상상사'),
                              wd(60, 22, '납부자번호'), wd(75, 22, '00000000000')])
    assert gov.recognizes(pages) is False
    assert set(rules(pages).values()) == {'LEGACY'}


@pytest.mark.parametrize('header_y,month_height,copies', [
    (200, 20, 3), (200, 10, 3), (225, 10, 3), (235, 10, 3), (238, 10, 3), (200, 20, 2), (225, 10, 4), (100, 60, 3)])
def test_current_shadow_equals_operating_route_on_authored_pages(header_y, month_height, copies):
    words = tokens(header_y=header_y, month_height=month_height, copies=copies)
    form, value = observe(canvas(), words, 'own')
    assert value['CURRENT'] == form
    assert gov.recognizes(prepare_pairs(canvas(), words, 'own')) is (form == 'GOVERNMENT')


def test_structure_block_stops_at_gap_group_row_and_non_header_line():
    # H = 10 px; first-month centre 255 px. The component line centre sits 1.3H above it.
    near = tokens(header_y=237, month_height=10)
    assert rules(prepare_pairs(canvas(), near, 'own'))['S'] == 'GOVERNMENT'
    far = tokens(header_y=225, month_height=10)
    assert rules(prepare_pairs(canvas(), far, 'own'))['S'] == 'LEGACY'
    for text in ('납부금액', '가상안내'):
        between = near + [OcrWord(text, .96, (400, 245, 480, 251))]
        assert rules(prepare_pairs(canvas(), between, 'own'))['S'] == 'LEGACY'


def test_path_without_payment_dispatch_keeps_actual_branch():
    def other(page, words, engine):
        return None, {}, 'OTHER'
    found = []
    route.inspect_extraction(canvas(), tokens(), 'own', other, found)
    assert found == [dict.fromkeys(shadow.RULES, 'OTHER')]


def test_rule_failure_is_a_fixed_error_branch(monkeypatch):
    def fail(*_):
        raise RuntimeError(SENTINEL)
    monkeypatch.setitem(shadow.SELECTIONS, 'S', fail)
    form, value = observe(canvas(), tokens(), 'own')
    assert value == {'CURRENT': form, 'OLD_CURRENT': form, 'A': 'LEGACY', 'S': 'ERROR'}


def test_end_to_end_shadow_rows_and_current_parity(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    assert invoke(root, out) == 0
    summary = json.loads((out/'summary.json').read_text())
    value = summary['shadow_routes']
    routes = {(r['rule'], r['engine'], r['form']): r['pages'] for r in value['routes'] if r['pages']}
    assert routes == {(rule, engine, 'GOVERNMENT' if rule in ('CURRENT', 'OLD_CURRENT') else 'LEGACY'): 1
                      for rule in shadow.RULES for engine in ('text_layer', 'own', 'applevision')}
    actual = {(r['engine'], r['form']): r['pages'] for r in summary['routes']['distributions']}
    assert all(actual[(engine, form)] == routes.get(('CURRENT', engine, form), 0)
               for engine, form in actual)
    assert value['checks'] == [dict(engine=engine, match=1, mismatch=0)
                               for engine in ('text_layer', 'own', 'applevision')]
    brief = (out/'summary_brief.txt').read_text()
    assert 'SHADOW_ROUTE CURRENT own GOVERNMENT 1\n' in brief
    assert 'SHADOW_ROUTE S own LEGACY 1\n' in brief
    assert 'SHADOW_ROUTE S own GOVERNMENT 0\n' in brief
    assert 'SHADOW_ROUTE S own ERROR' not in brief
    assert 'SHADOW_CROSS A applevision LEGACY LEGACY 1\n' in brief
    assert 'SHADOW_CROSS CURRENT own GOVERNMENT GOVERNMENT 1\n' in brief
    assert 'SHADOW_CROSS S own GOVERNMENT' not in brief
    assert 'SHADOW_CHECK CURRENT own MATCH 1 MISMATCH 0\n' in brief
    text = (out/'summary.txt').read_text()
    assert 'SHADOW_ROUTE S own ERROR 0\n' in text and 'SHADOW_CROSS S own GOVERNMENT GOVERNMENT 0\n' in text
    shadow_lines = [line for line in brief.splitlines() if line.startswith('SHADOW')]
    assert all(line.split()[0] in ('SHADOW_RULES', 'SHADOW_ROUTE', 'SHADOW_CROSS', 'SHADOW_CHECK')
               for line in shadow_lines)
    assert all(token.isdigit() or token in (*shadow.RULES, *shadow.BRANCHES, 'text_layer', 'own',
               'applevision', 'MATCH', 'MISMATCH') for line in shadow_lines for token in line.split()[1:])
    assert_private_output(out, capfd)


def test_rule_error_or_current_mismatch_sets_failure_exit(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    original = shadow.branches
    monkeypatch.setattr(shadow, 'branches', lambda pairs, actual: {**original(pairs, actual), 'CURRENT': 'LEGACY'})
    assert invoke(root, out) == 1
    value = json.loads((out/'summary.json').read_text())['shadow_routes']
    assert [item['mismatch'] for item in value['checks']] == [1, 1, 1]
    assert_private_output(out, capfd)


def observation(document, engine, current='LEGACY', a='LEGACY', s='LEGACY', form='LEGACY'):
    return dict(document=document, page=1, engine=engine, form=form,
                rules={'CURRENT': current, 'OLD_CURRENT': current, 'A': a, 'S': s})


def test_cross_uses_same_rule_text_layer_branch_and_counts_each_page_once():
    meta = {'engines': ['own']}
    observations = [observation(1, 'text_layer', 'GOVERNMENT', form='GOVERNMENT'),
                    observation(1, 'own', 'GOVERNMENT', 'GOVERNMENT', form='GOVERNMENT'),
                    observation(2, 'text_layer'), observation(2, 'own', s='GOVERNMENT'),
                    observation(3, 'own')]
    value = shadow.build_summary(meta, observations)
    shadow.validate_summary(value)
    cross = {(r['rule'], r['reference_form'], r['form']): r['pages'] for r in value['cross'] if r['pages']}
    assert cross == {('CURRENT', 'GOVERNMENT', 'GOVERNMENT'): 1, ('CURRENT', 'LEGACY', 'LEGACY'): 1,
                     ('OLD_CURRENT', 'GOVERNMENT', 'GOVERNMENT'): 1, ('OLD_CURRENT', 'LEGACY', 'LEGACY'): 1,
                     ('A', 'LEGACY', 'GOVERNMENT'): 1, ('A', 'LEGACY', 'LEGACY'): 1,
                     ('S', 'LEGACY', 'LEGACY'): 1, ('S', 'LEGACY', 'GOVERNMENT'): 1}
    routes = {(r['rule'], r['engine'], r['form']): r['pages'] for r in value['routes'] if r['pages']}
    assert routes[('S', 'own', 'LEGACY')] == 2 and routes[('S', 'own', 'GOVERNMENT')] == 1
    assert len(value['routes']) == len(shadow.RULES) * 2 * len(shadow.BRANCHES)
    assert value['checks'] == [dict(engine='text_layer', match=2, mismatch=0), dict(engine='own', match=3, mismatch=0)]
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_summary(meta, observations + [observation(3, 'own')])


@pytest.mark.parametrize('mutation', ['unknown-key', 'unknown-rule', 'unknown-branch', 'bool-count', 'float-count', 'engine'])
def test_shadow_summary_closed_schema(mutation):
    meta = {'engines': ['own'], 'fields': []}
    rows = [tool.row(1, 1, 'NHIS_PAYMENT', 'LEGACY')]
    observations = [observation(1, 'text_layer'), observation(1, 'own')]
    value = tool.build_summary(meta, rows, dict.fromkeys(tool.COUNTERS, 0), (), observations)
    tool.validate_summary(deepcopy(value), meta, rows, (), observations)
    target = value['shadow_routes']
    if mutation == 'unknown-key':
        target[SENTINEL] = 0
    elif mutation == 'unknown-rule':
        target['routes'][0]['rule'] = SENTINEL
    elif mutation == 'unknown-branch':
        target['cross'][0]['form'] = SENTINEL
    elif mutation == 'bool-count':
        target['checks'][0]['match'] = True
    elif mutation == 'float-count':
        target['routes'][0]['pages'] = 0.0
    else:
        target['checks'][0]['engine'] = SENTINEL
    with pytest.raises((tool.DiagnosticError, shadow.ShadowRouteError)):
        tool.validate_summary(value, meta, rows, (), observations)
    with pytest.raises(shadow.ShadowRouteError):
        shadow.validate_summary(target)


@pytest.mark.parametrize('bad', [
    dict(rules={'CURRENT': 'LEGACY', 'A': 'LEGACY'}), dict(rules={'CURRENT': 'LEGACY', 'A': 'LEGACY', 'S': SENTINEL}),
    dict(form=SENTINEL), dict(engine=SENTINEL), dict(page=0), dict(extra=SENTINEL)])
def test_shadow_observation_is_closed(bad):
    item = {**observation(1, 'own'), **bad}
    with pytest.raises(shadow.ShadowRouteError):
        shadow.build_summary({'engines': ['own']}, [item])
