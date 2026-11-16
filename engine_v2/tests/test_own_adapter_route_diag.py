"""Independent routing-condition, CLI and value-free aggregate checks."""
from copy import deepcopy
import json

import pytest

from engine_v2.pipeline.ocr import OcrResult, OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tools import own_adapter_diag as tool
from engine_v2.tools import own_adapter_diag_evidence as evidence
from engine_v2.tools import own_adapter_route_diag as route
from engine_v2.tools import ocr_baseline_runtime as runtime
from engine_v2.tools.ocr_baseline_fields import prepare_pairs
from engine_v2.tests.test_own_adapter_diag import pdf, fake_recognize, read_rows

SENTINEL = 'SYNTHETIC_ROUTE_SECRET_618537'


def canvas():
    return PageImage(0, PageSource.TEXT_LAYER, (240, 240), pixel_size=(1000, 1000), dpi=300)


def word(text, x, y, height=10, width=80):
    return OcrWord(text, .96, (x, y, x + width, y + height))


def tokens(*, copies=3, component='보수외소득월액(건강)', header_y=200, month_height=20):
    return [
        word('건강보험료납부확인서', 50, 20, width=180),
        word('문서확인번호', 50, 60), word('1234-5678-9012-3456', 250, 60, width=200),
        word('납부자번호', 50, 100), word('사업장명칭', 250, 100),
        *(word(component, 50 + index * 90, header_y) for index in range(copies)),
        word('1월', 50, 250, height=month_height),
    ]


def analyze(words=None, **kwargs):
    return route.analyze(prepare_pairs(canvas(), tokens() if words is None else words, 'own'), True, **kwargs)


@pytest.fixture
def locations(tmp_path):
    root, out = tmp_path/'input', tmp_path/'output'
    root.mkdir()
    return root, out


def install_payment(monkeypatch, root, *, operation=None):
    path = pdf(root/f'{SENTINEL}.pdf')
    monkeypatch.setattr(runtime, 'reference_page', lambda *_: (canvas(), deepcopy(tokens())))
    fake_recognize(monkeypatch, path, operation=operation)
    return path


def invoke(root, out, *args):
    return tool.main(['--root', str(root), '--out', str(out), *args])


def assert_private_output(out, capfd):
    captured = capfd.readouterr()
    assert captured.err == '' and SENTINEL not in captured.out
    if out.exists():
        assert all(SENTINEL not in path.read_text() for path in out.iterdir())


def test_complete_government_formula_uses_independent_atoms():
    value = analyze()
    assert value['status'] == 'MEASURED'
    assert list(value['flags']) == list(route.CONDITIONS)
    assert all(value['flags'].values())
    assert value['bins']['HEADER_BOSUOE_COUNT'] == value['bins']['HEADER_INCOME_COUNT'] == 'N3'
    assert value['bins']['HEADER_HEIGHT_RATIO'] == 'R005_010'


@pytest.mark.parametrize('removed,condition,gate', [
    ('문서확인번호', 'DOCUMENT_NUMBER_LABEL', 'GOV_NUMBER_GATE'),
    ('1234-5678-9012-3456', 'DOCUMENT_NUMBER_PATTERN', 'GOV_NUMBER_GATE'),
    ('납부자번호', 'PAYER_NUMBER_LABEL', 'INFO_GRID_GATE'),
    ('사업장명칭', 'WORKPLACE_LABEL', 'INFO_GRID_GATE'),
])
def test_metadata_atoms_and_alternative_gates(removed, condition, gate):
    value = analyze([w for w in tokens() if w.text != removed])
    assert value['flags'][condition] is False and value['flags'][gate] is False
    assert value['flags']['GOV_PREDICATE'] is True


@pytest.mark.parametrize('title,government,legacy', [
    ('건강보험료납부확인서', True, True),
    ('건강보험료납부확인', False, True),
    ('가상서류', False, False),
])
def test_title_gates_do_not_promote_legacy_validation_to_route_selection(title, government, legacy):
    words = tokens()
    words[0].text = title
    flags = analyze(words)['flags']
    assert flags['GOV_TITLE'] is government and flags['LEGACY_TITLE'] is legacy
    assert flags['GOV_PREDICATE'] is government


def test_both_metadata_alternatives_must_fail_to_block_government():
    words = [w for w in tokens() if w.text not in ('문서확인번호', '사업장명칭')]
    flags = analyze(words)['flags']
    assert flags['GOV_NUMBER_GATE'] is flags['INFO_GRID_GATE'] is flags['GOV_PREDICATE'] is False


@pytest.mark.parametrize('copies,expected,bucket', [(2, False, 'N2'), (3, True, 'N3'), (4, True, 'N4_9'), (10, True, 'GE10')])
def test_header_count_thresholds(copies, expected, bucket):
    value = analyze(tokens(copies=copies))
    assert value['flags']['HEADER_BOSUOE_GE3'] is value['flags']['HEADER_INCOME_GE3'] is expected
    assert value['flags']['GOV_PREDICATE'] is expected
    assert value['bins']['HEADER_BOSUOE_COUNT'] == value['bins']['HEADER_INCOME_COUNT'] == bucket


@pytest.mark.parametrize('component,true_code,false_code', [
    ('보수외', 'HEADER_BOSUOE_GE3', 'HEADER_INCOME_GE3'),
    ('소득월액', 'HEADER_INCOME_GE3', 'HEADER_BOSUOE_GE3'),
])
def test_each_repeated_header_condition_is_independent(component, true_code, false_code):
    flags = analyze(tokens(component=component))['flags']
    assert flags[true_code] is True and flags[false_code] is False
    assert flags['GOV_PREDICATE'] is False


def test_missing_component_boundary_is_distinct_from_missing_month():
    value = analyze(tokens(component='다른머리글'))
    assert value['flags']['COMPONENT_TOP_FOUND'] is False
    assert value['flags']['FIRST_MONTH_FOUND'] is False
    assert value['bins']['HEADER_HEIGHT_RATIO'] == 'NA'
    assert value['bins']['HEADER_BOSUOE_COUNT'] == 'N0'


def test_header_band_can_miss_component_top_with_a_valid_first_month():
    value = analyze(tokens(header_y=100))
    assert value['flags']['COMPONENT_TOP_FOUND'] is value['flags']['FIRST_MONTH_FOUND'] is True
    assert value['flags']['HEADER_COMPONENT_TOP_FOUND'] is False
    assert value['bins']['HEADER_INCOME_COUNT'] == 'N0'


def test_taller_month_box_widens_search_band_and_changes_original_predicate():
    short = analyze(tokens(header_y=150, month_height=20))
    tall = analyze(tokens(header_y=150, month_height=40))
    assert short['flags']['GOV_PREDICATE'] is False
    assert tall['flags']['GOV_PREDICATE'] is True
    assert short['bins']['HEADER_HEIGHT_RATIO'] == 'R005_010'
    assert tall['bins']['HEADER_HEIGHT_RATIO'] == 'R010_025'
    assert short['bins']['HEADER_BOSUOE_COUNT'] == 'N0'
    assert tall['bins']['HEADER_BOSUOE_COUNT'] == 'N3'


@pytest.mark.parametrize('month', ['1월 10000', '1월10000', '월', '13월'])
def test_month_fullmatch_rejects_fused_or_invalid_boxes(month):
    words = tokens()
    words[-1].text = month
    value = analyze(words)
    assert value['flags']['COMPONENT_TOP_FOUND'] is True
    assert value['flags']['FIRST_MONTH_FOUND'] is value['flags']['GOV_PREDICATE'] is False
    assert value['bins']['HEADER_HEIGHT_RATIO'] == 'NA'


@pytest.mark.parametrize('month', ['1월', '01월', '12월', '１월', '1 월'])
def test_shared_normalization_and_month_grammar(month):
    words = tokens()
    words[-1].text = month
    assert analyze(words)['flags']['FIRST_MONTH_FOUND'] is True


@pytest.mark.parametrize('metric,boundary,below,at', [
    ('HEADER_BOSUOE_COUNT', 1, 'N0', 'N1'),
    ('HEADER_BOSUOE_COUNT', 2, 'N1', 'N2'),
    ('HEADER_BOSUOE_COUNT', 3, 'N2', 'N3'),
    ('HEADER_BOSUOE_COUNT', 4, 'N3', 'N4_9'),
    ('HEADER_BOSUOE_COUNT', 10, 'N4_9', 'GE10'),
    ('HEADER_HEIGHT_RATIO', .01, 'LT_001', 'R001_002'),
    ('HEADER_HEIGHT_RATIO', .02, 'R001_002', 'R002_005'),
    ('HEADER_HEIGHT_RATIO', .05, 'R002_005', 'R005_010'),
    ('HEADER_HEIGHT_RATIO', .10, 'R005_010', 'R010_025'),
    ('HEADER_HEIGHT_RATIO', .25, 'R010_025', 'GE_025'),
    ('BOX_HEIGHT_MEDIAN_RATIO', .005, 'LT_0005', 'R0005_001'),
    ('BOX_HEIGHT_MEDIAN_RATIO', .01, 'R0005_001', 'R001_002'),
    ('BOX_HEIGHT_MEDIAN_RATIO', .02, 'R001_002', 'R002_005'),
    ('BOX_HEIGHT_MEDIAN_RATIO', .05, 'R002_005', 'R005_010'),
    ('BOX_HEIGHT_MEDIAN_RATIO', .10, 'R005_010', 'GE_010'),
    ('BOX_CHAR_MEDIAN', 1, 'LT1', 'R1_4'),
    ('BOX_CHAR_MEDIAN', 4, 'R1_4', 'R4_8'),
    ('BOX_CHAR_MEDIAN', 8, 'R4_8', 'R8_16'),
    ('BOX_CHAR_MEDIAN', 16, 'R8_16', 'R16_32'),
    ('BOX_CHAR_MEDIAN', 32, 'R16_32', 'R32_64'),
    ('BOX_CHAR_MEDIAN', 64, 'R32_64', 'GE64'),
    ('PAGE_BOX_COUNT', 1, 'ZERO', 'N1_49'),
    ('PAGE_BOX_COUNT', 50, 'N1_49', 'N50_99'),
    ('PAGE_BOX_COUNT', 100, 'N50_99', 'N100_199'),
    ('PAGE_BOX_COUNT', 200, 'N100_199', 'N200_399'),
    ('PAGE_BOX_COUNT', 400, 'N200_399', 'N400_799'),
    ('PAGE_BOX_COUNT', 800, 'N400_799', 'GE800'),
])
def test_histogram_boundaries_are_half_open(metric, boundary, below, at):
    assert route.bin_value(metric, boundary - min(.000001, boundary / 2)) == below
    assert route.bin_value(metric, boundary) == at


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True, SENTINEL])
def test_invalid_raw_measurement_is_rejected(value):
    with pytest.raises(route.RouteDiagnosticError):
        route.bin_value('BOX_CHAR_MEDIAN', value)


def test_no_boxes_has_explicit_na_medians_and_zero_count():
    value = analyze([])
    assert value['bins']['BOX_CHAR_MEDIAN'] == value['bins']['BOX_HEIGHT_MEDIAN_RATIO'] == 'NA'
    assert value['bins']['PAGE_BOX_COUNT'] == 'ZERO'


@pytest.mark.parametrize('invalid', ['pixel-size', 'nonfinite', 'empty-box'])
def test_invalid_geometry_cannot_be_reported_as_a_measured_pattern(invalid):
    page, words = canvas(), tokens()
    if invalid == 'pixel-size':
        page.pixel_size = (0, 1000)
    elif invalid == 'nonfinite':
        words[0].bbox_px = (0, 0, float('nan'), 10)
    else:
        words[0].bbox_px = (0, 0, 0, 10)
    with pytest.raises(route.RouteDiagnosticError):
        route.analyze(prepare_pairs(page, words, 'own'), True)


@pytest.mark.parametrize('engine', ['text_layer', 'own', 'applevision'])
def test_actual_extraction_parity_and_input_preservation(engine):
    page, words = canvas(), tokens()
    before = deepcopy(words)
    with tool.batch.guarded():
        expected = evidence.extract_with_form(page, words, engine)
        actual, observation = route.inspect_extraction(page, words, engine, evidence.extract_with_form)
    assert actual[0].fields == expected[0].fields and actual[1:] == expected[1:]
    assert actual[2] == 'GOVERNMENT'
    assert observation['status'] == 'MEASURED' and observation['flags']['GOV_PREDICATE'] is True
    assert words == before


@pytest.mark.parametrize('failure', ['exception', 'interrupt'])
def test_primary_observation_wrappers_restore_after_failure(failure):
    from engine_v2.extractors import nhis_payment, nhis_payment_gov
    originals = nhis_payment.extract, nhis_payment_gov.recognizes

    def fail(*args):
        raise RuntimeError(SENTINEL) if failure == 'exception' else KeyboardInterrupt()

    with pytest.raises(RuntimeError if failure == 'exception' else KeyboardInterrupt):
        route.inspect_extraction(canvas(), tokens(), 'own', fail)
    assert (nhis_payment.extract, nhis_payment_gov.recognizes) == originals


def test_prospective_other_does_not_claim_payment_dispatch():
    def other(*args):
        return object(), {}, 'OTHER'

    _, value = route.inspect_extraction(canvas(), tokens(), 'own', other)
    assert value['status'] == 'PROSPECTIVE'
    assert value['flags']['PAYMENT_DISPATCH_CALLED'] is False
    assert value['flags']['GOV_PREDICATE'] is True


def test_original_predicate_disagreement_is_explicit():
    with pytest.raises(route.RouteDiagnosticError, match='PREDICATE_DIVERGENCE'):
        analyze(original_result=False)


@pytest.mark.parametrize('status', ['CONDITION_ERROR', 'PREDICATE_DIVERGENCE'])
def test_analysis_failure_preserves_original_extraction(locations, monkeypatch, capfd, status):
    root, out = locations
    install_payment(monkeypatch, root)

    def fail(*args):
        if status == 'PREDICATE_DIVERGENCE':
            raise route.RouteDiagnosticError(status)
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(route, 'analyze', fail)
    assert invoke(root, out) == 1
    rows = read_rows(out)
    assert all(row['code'] not in tool.ERRORS for row in rows)
    summary = json.loads((out/'summary.json').read_text())
    assert summary['counters']['execution_errors'] == 0
    groups = [group for group in summary['route_conditions']['groups'] if group['pages']]
    assert len(groups) == 3 and all(group['statuses'][status] == 1 for group in groups)
    assert all(not group['patterns'] for group in groups)
    assert_private_output(out, capfd)


def test_field_evidence_replays_do_not_add_primary_route_observations(locations, monkeypatch):
    from engine_v2.tests.test_own_adapter_diag_codes import tokens as legacy_tokens, page as legacy_page
    root, out = locations
    path = pdf(root/'authored.pdf')
    monkeypatch.setattr(runtime, 'reference_page', lambda *_: (legacy_page(), legacy_tokens()))

    def remove_date(engine, page, words):
        observed = [word for word in words if word.text != '2026.11.10']
        return OcrResult(engine, observed), observed, {}

    fake_recognize(monkeypatch, path, operation=remove_date)
    replay_calls = []

    def diagnose(page, truth, observed, kind, key, reference, actual, observed_kind, engine, *forms):
        runtime.extract(page, observed, engine)
        replay_calls.append(engine)
        return 'OTHER'

    monkeypatch.setattr(evidence, 'diagnose', diagnose)
    assert invoke(root, out) == 0
    assert replay_calls
    summary = json.loads((out/'summary.json').read_text())
    groups = [g for g in summary['route_conditions']['groups'] if g['pages']]
    assert len(groups) == 3
    assert all(g['statuses']['MEASURED'] == 1 and sum(p['pages'] for p in g['patterns']) == 1 for g in groups)


def test_rejected_document_guard_discards_condition_observations(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    marker = root.parent/SENTINEL
    original = route.analyze

    def swallowed_write(*args, **kwargs):
        try:
            marker.write_text(SENTINEL)
        except OSError:
            pass
        return original(*args, **kwargs)

    monkeypatch.setattr(route, 'analyze', swallowed_write)
    assert invoke(root, out) == 1
    assert not marker.exists()
    rows = read_rows(out)
    assert len(rows) == 1 and rows[0]['code'] == 'PROCESSING_ERROR'
    summary = json.loads((out/'summary.json').read_text())
    assert all(g['pages'] == 0 and not g['patterns'] for g in summary['route_conditions']['groups'])
    assert_private_output(out, capfd)


@pytest.mark.parametrize('state,expected', [('empty', 'EMPTY_OCR'), ('unavailable', 'ENGINE_UNAVAILABLE'), ('error', 'OCR_ERROR')])
def test_missing_ocr_paths_have_status_counts_and_zero_condition_patterns(locations, monkeypatch, state, expected):
    root, out = locations

    def operation(engine, page, words):
        if state == 'empty':
            return OcrResult(engine, []), [], {}
        if state == 'unavailable':
            raise ImportError()
        raise RuntimeError()

    install_payment(monkeypatch, root, operation=operation)
    assert invoke(root, out) == int(state == 'error')
    summary = json.loads((out/'summary.json').read_text())
    groups = [g for g in summary['route_conditions']['groups'] if g['pages'] and g['engine'] != 'text_layer']
    assert len(groups) == 2
    assert all(g['statuses'][expected] == 1 and not g['patterns'] for g in groups)
    assert all(sum(pair.values()) == 0 for g in groups for pair in g['conditions'].values())


def test_brief_contains_routes_bins_patterns_and_only_nonzero_field_codes(locations, monkeypatch, capfd):
    root, out = locations
    install_payment(monkeypatch, root)
    assert invoke(root, out) == 0
    summary = json.loads((out/'summary.json').read_text())
    groups = [g for g in summary['route_conditions']['groups'] if g['pages']]
    assert len(groups) == 3 and all(g['pages'] == g['statuses']['MEASURED'] == 1 for g in groups)
    assert all(sum(p['pages'] for p in g['patterns']) == 1 for g in groups)
    brief = (out/'summary_brief.txt').read_text()
    assert 'ROUTE own GOVERNMENT 1\n' in brief
    assert 'ROUTE_CROSS own GOVERNMENT GOVERNMENT 1\n' in brief
    assert 'CONDITION_ORDER ' + ' '.join(route.CONDITIONS) in brief
    assert 'BIN HEADER_HEIGHT_RATIO R005_010 0.05 0.1\n' in brief
    assert 'CONDITION GOVERNMENT own FIRST_MONTH_FOUND O 1\n' in brief
    assert 'DISTRIBUTION GOVERNMENT own HEADER_BOSUOE_COUNT N3 1\n' in brief
    assert 'CONDITION_PATTERN GOVERNMENT own ' in brief
    field_lines = [line for line in brief.splitlines() if line.startswith('FIELD ')]
    assert field_lines and all(int(line.split()[-1]) > 0 for line in field_lines)
    assert sum(int(line.split()[-1]) for line in field_lines) == len(read_rows(out))
    assert set(json.loads((out/'run.json').read_text())) == {'schema_version', 'engines', 'fields', 'clean', 'limit'}
    assert all(set(row) == tool.ROW_KEYS for row in read_rows(out))
    assert_private_output(out, capfd)


@pytest.mark.parametrize('mutation', ['unknown-key', 'unknown-condition', 'unknown-bin', 'bool-count', 'pattern', 'population'])
def test_condition_summary_closed_schema(mutation):
    meta = {'engines': ['own'], 'fields': []}
    rows = [tool.row(1, 1, 'NHIS_PAYMENT', 'GOVERNMENT')]
    observations = []
    route.record(observations, 1, 1, 'own', 'GOVERNMENT', 'GOVERNMENT', analyze())
    value = tool.build_summary(meta, rows, dict.fromkeys(tool.COUNTERS, 0), observations)
    group = next(g for g in value['route_conditions']['groups'] if g['engine'] == 'own' and g['pages'])
    if mutation == 'unknown-key':
        group[SENTINEL] = 0
    elif mutation == 'unknown-condition':
        group['conditions'][SENTINEL] = {'O': 1, 'X': 0}
    elif mutation == 'unknown-bin':
        group['distributions']['BOX_CHAR_MEDIAN'][SENTINEL] = 1
    elif mutation == 'bool-count':
        group['conditions']['GOV_TITLE']['O'] = True
    elif mutation == 'pattern':
        group['patterns'][0]['pattern'] = SENTINEL
    else:
        group['pages'] += 1
    with pytest.raises((tool.DiagnosticError, route.RouteDiagnosticError)):
        tool.validate_summary(value, meta, rows, observations)


def test_duplicate_observation_is_rejected_instead_of_double_counting_fields():
    rows = [tool.row(1, 1, 'NHIS_PAYMENT', 'GOVERNMENT')]
    observations = []
    route.record(observations, 1, 1, 'own', 'GOVERNMENT', 'GOVERNMENT', analyze())
    observations *= 2
    with pytest.raises(route.RouteDiagnosticError):
        route.build_summary({'engines': ['own']}, rows, observations)


@pytest.mark.parametrize('mode,expected', [
    ('root-missing', 'ROOT_NOT_DIR'), ('root-file', 'ROOT_NOT_DIR'),
    ('out-dir', 'OUT_EXISTS'), ('out-file', 'OUT_EXISTS'),
    ('out-inside', 'OUT_INSIDE_ROOT'), ('out-equal', 'OUT_INSIDE_ROOT'),
    ('root-inside', 'ROOT_INSIDE_OUT'), ('ids-missing', 'IDS_NOT_FOUND'),
    ('ids-dir', 'IDS_INVALID'), ('ids-hardlink', 'IDS_INVALID'), ('ids-pdf', 'IDS_INVALID'),
])
def test_specific_location_errors_have_no_input_values(locations, mode, expected, capfd):
    import os
    root, out = locations
    args = []
    if mode == 'root-missing':
        root = root/SENTINEL
    elif mode == 'root-file':
        root = root.parent/SENTINEL
        root.write_text(SENTINEL)
    elif mode == 'out-dir':
        out.mkdir()
    elif mode == 'out-file':
        out.write_text(SENTINEL)
    elif mode == 'out-inside':
        out = root/SENTINEL
    elif mode == 'out-equal':
        out = root
    elif mode == 'root-inside':
        out = root.parent
    elif mode == 'ids-missing':
        args = ['--ids', str(root/SENTINEL)]
    elif mode == 'ids-dir':
        args = ['--ids', str(root)]
    elif mode == 'ids-hardlink':
        original = root/SENTINEL
        original.write_text(SENTINEL)
        linked = root.parent/'selection'
        os.link(original, linked)
        args = ['--ids', str(linked)]
    elif mode == 'ids-pdf':
        source = pdf(root/f'{SENTINEL}.pdf')
        args = ['--ids', str(source)]
    assert invoke(root, out, *args) == 2
    captured = capfd.readouterr()
    assert captured.err == ''
    assert json.loads(captured.out) == {'code': expected}


@pytest.mark.parametrize('argument', ['root', 'out', 'ids'])
@pytest.mark.parametrize('dangling', [False, True])
def test_explicit_symlink_arguments_are_rejected(locations, argument, dangling, capfd):
    root, out = locations
    target = root.parent/SENTINEL
    if not dangling:
        target.mkdir()
    linked = root.parent/'link'
    linked.symlink_to(target, target_is_directory=True)
    args = []
    if argument == 'root':
        root = linked
    elif argument == 'out':
        out = linked
    else:
        args = ['--ids', str(linked)]
    assert invoke(root, out, *args) == 2
    assert json.loads(capfd.readouterr().out) == {'code': 'SYMLINK_REJECTED'}


@pytest.mark.parametrize('error,expected', [('location', 'LOCATION_REJECTED'), ('output', 'OUTPUT_ERROR')])
def test_fixed_internal_error_codes_remain_value_free(locations, monkeypatch, capfd, error, expected):
    root, out = locations

    def fail(*args, **kwargs):
        raise tool.batch.BatchError(expected) if error == 'location' else tool.DiagnosticError(expected)

    monkeypatch.setattr(tool, 'run', fail)
    assert invoke(root, out) == 2
    assert json.loads(capfd.readouterr().out) == {'code': expected}


def test_argument_parse_error_is_distinct(capfd):
    assert tool.main([f'--{SENTINEL}']) == 2
    captured = capfd.readouterr()
    assert captured.err == '' and json.loads(captured.out) == {'code': 'ARGUMENT_ERROR'}


def test_unexpected_error_reports_only_reviewed_base_exception_type(monkeypatch, capfd):
    custom = type(SENTINEL, (RuntimeError,), {})

    def fail(*args, **kwargs):
        raise custom(SENTINEL)

    monkeypatch.setattr(tool, 'run', fail)
    assert tool.main(['--root', SENTINEL, '--out', SENTINEL]) == 2
    captured = capfd.readouterr()
    assert captured.err == ''
    assert json.loads(captured.out) == {'code': 'UNEXPECTED_ERROR', 'exception_type': 'RuntimeError'}


def test_help_is_static_and_successful_without_filesystem_or_ocr(monkeypatch, capfd):
    def fail(*args, **kwargs):
        pytest.fail('help accessed runtime')

    monkeypatch.setattr(tool, 'run', fail)
    assert tool.main(['--help', '--root', SENTINEL]) == 0
    captured = capfd.readouterr()
    assert captured.err == '' and SENTINEL not in captured.out
    assert 'usage: own_adapter_diag' in captured.out and '--engines' in captured.out


def test_help_through_module_entry_point_exits_zero():
    import subprocess
    import sys
    completed = subprocess.run([sys.executable, '-B', '-m', 'engine_v2.tools.own_adapter_diag', '--help'],
                               capture_output=True, text=True)
    assert completed.returncode == 0 and completed.stderr == ''
    assert 'usage: own_adapter_diag' in completed.stdout
    assert SENTINEL not in completed.stdout
