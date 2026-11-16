"""Independent checks of the read-only, value-free ocr_baseline result comparison."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tools import batch_assess as batch
from engine_v2.tools import ocr_baseline as baseline
from engine_v2.tools import ocr_baseline_compare as tool
from engine_v2.tools.ocr_baseline_metrics import measure
from engine_v2.tools.ocr_baseline_settings import SETTINGS

SENTINEL = 'SYNTHETIC_COMPARE_SECRET_204871'
REPOSITORY = Path(__file__).resolve().parents[2]


def metrics(observed='가상문자'):
    reference = [OcrWord('가상문자', .99, (10, 10, 90, 30))]
    words = [OcrWord(observed, .99, (10, 10, 90, 30))] if observed else []
    return measure(reference, words, (100, 100))


def item(engine, variant, *, match=1, ocr=1.0, observed='가상문자', kind='NHIS_PAYMENT', missing=()):
    fields = {}
    for key in batch.FIELDS[kind]:
        eligible = int(key not in missing)
        hit = match if eligible else 0
        fields[key] = dict(eligible=eligible, match=hit, missing_reference=1 - eligible,
                           ocr_cause=eligible - hit, structure_cause=0, unattributable=0)
    seconds = dict(deepcopy(baseline.TIMING), ocr=ocr, extraction=.25, total=ocr + .25)
    return dict(engine=engine, variant=variant, state='OK', code='NONE', type_match=1,
                metrics=metrics(observed), fields=fields, seconds=seconds)


def row(identifier, measurements, kind='NHIS_PAYMENT'):
    page = dict(page=1, type=kind, exclusion='NONE', quality=dict(baseline.QUALITY), seed=7,
                reference_seconds=.1, measurements=measurements)
    return dict(schema_version=baseline.VERSION, id=identifier, page_count=1, code='NONE', pages=[page])


def write(directory, rows, *, digest='a' * 64, engines=('own',), variants=('clean',), settings=SETTINGS):
    directory.mkdir()
    meta = dict(schema_version=baseline.VERSION, root_digest=digest, engines=list(engines),
                variants=list(variants), settings=settings)
    (directory / 'run.json').write_text(json.dumps(meta, ensure_ascii=False))
    (directory / 'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    return directory


def run(capfd, *args):
    code = tool.main([str(a) for a in args])
    captured = capfd.readouterr()
    assert captured.err == ''
    return code, captured.out


def lines(out, prefix):
    return [line for line in out.splitlines() if line.startswith(prefix)]


def test_rates_use_percentage_points_and_time_uses_seconds(tmp_path, capfd):
    before = write(tmp_path / 'b', [row(f'{SENTINEL}/1.pdf', [item('own', 'clean', match=1, ocr=1.0)])])
    after = write(tmp_path / 'a', [row(f'{SENTINEL}/1.pdf', [item('own', 'clean', match=0, ocr=1.5)])])
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0
    assert 'FIELD NHIS_PAYMENT MEMBERSHIP own clean 1 1 100.000000 0 1 0.000000 -100.000000' in out
    assert 'TIME NHIS_PAYMENT own clean OCR_TIME_PER_PAGE_S 1.000000 1.500000 0.500000 1 1 1 1' in out
    assert 'TIME NHIS_PAYMENT own clean TOTAL_TIME_PER_PAGE_S 1.250000 1.750000 0.500000 1 1 1 1' in out
    assert 'RECOGNITION NHIS_PAYMENT own clean PAGE_CER_MEAN 0.000000 0.000000 0.000000 1 1' in out
    assert 'RECOGNITION NHIS_PAYMENT own clean WORD_F1 100.000000 100.000000 0.000000 1 1' in out
    assert lines(out, 'COHORT DOCUMENTS') == ['COHORT DOCUMENTS 1 1 1 0 0']


def test_unmeasured_grid_and_zero_denominators_are_explicit_na(tmp_path, capfd):
    rows = [row('1.pdf', [item('own', 'clean', missing=('가입구분',))])]
    before, after = write(tmp_path / 'b', rows), write(tmp_path / 'a', rows)
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0
    assert 'FIELD NHIS_PAYMENT MEMBERSHIP own clean 0 0 NA 0 0 NA NA' in out
    assert 'FIELD ADMIN_INFO_CONSENT NAME own clean 0 0 NA 0 0 NA NA' in out
    assert 'RECOGNITION ADMIN_INFO_CONSENT own clean POOLED_CER NA NA NA 0 0' in out
    assert 'TIME ADMIN_INFO_CONSENT own clean OCR_TIME_PER_PAGE_S NA NA NA 0 0 0 0' in out
    kinds = sorted(batch.FIELDS)
    assert lines(out, 'GRID FIELD') == [f'GRID FIELD {sum(len(batch.FIELDS[k]) for k in kinds)} '
                                        f'{len(batch.FIELDS["NHIS_PAYMENT"]) - 1}']
    assert lines(out, 'GRID GROUP') == [f'GRID GROUP {len(kinds)} 1']


def test_cer_above_one_and_negative_differences_are_preserved(tmp_path, capfd):
    before = write(tmp_path / 'b', [row('1.pdf', [item('own', 'clean', observed='가상문자가상문자가상문자')])])
    after = write(tmp_path / 'a', [row('1.pdf', [item('own', 'clean')])])
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0
    [pooled] = lines(out, 'RECOGNITION NHIS_PAYMENT own clean POOLED_CER')
    values = pooled.split()
    assert float(values[5]) == pytest.approx(200.0) and float(values[7]) == pytest.approx(-200.0)


def test_partial_cohorts_and_configuration_differences_are_counted(tmp_path, capfd):
    before = write(tmp_path / 'b', [row('1.pdf', [item('own', 'clean')]), row('2.pdf', [item('own', 'clean')])])
    after = write(tmp_path / 'a', [row('2.pdf', [item('own', 'clean'), item('applevision', 'clean')]),
                                   row('3.pdf', [item('own', 'clean', kind='NHIS_QUALIFICATION'),
                                                 item('applevision', 'clean', kind='NHIS_QUALIFICATION')],
                                       kind='NHIS_QUALIFICATION')],
                  digest='b' * 64, engines=('own', 'applevision'))
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0
    assert 'ROOT_DIGEST DIFFERENT' in out and 'ENGINES DIFFERENT' in out and 'VARIANTS SAME' in out
    assert 'COHORT DOCUMENTS 2 2 1 1 1' in out
    assert 'COHORT PAGES 2 2 1 1 1' in out
    assert 'COHORT MEASUREMENTS 2 4 1 1 3' in out
    assert 'FIELD NHIS_PAYMENT MEMBERSHIP applevision clean 0 0 NA 1 1 100.000000 NA' in out


def test_changed_page_type_is_counted(tmp_path, capfd):
    before = write(tmp_path / 'b', [row('1.pdf', [item('own', 'clean')])])
    after = write(tmp_path / 'a', [row('1.pdf', [item('own', 'clean', kind='NHIS_QUALIFICATION')],
                                       kind='NHIS_QUALIFICATION')])
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0 and 'COHORT TYPE_CHANGED_PAGES 1' in out


@pytest.mark.parametrize('damage', ['duplicate', 'corrupt', 'settings', 'unknown_key', 'missing_results'])
def test_invalid_results_are_rejected_with_fixed_codes(tmp_path, capfd, damage):
    good = write(tmp_path / 'good', [row(f'{SENTINEL}.pdf', [item('own', 'clean')])])
    bad = write(tmp_path / 'bad', [row(f'{SENTINEL}.pdf', [item('own', 'clean')])],
                settings={**SETTINGS, 'lines': {**SETTINGS['lines'], 'tolerance': 99}} if damage == 'settings'
                else SETTINGS)
    results = bad / 'results.jsonl'
    if damage == 'duplicate':
        results.write_text(results.read_text() * 2)
    elif damage == 'corrupt':
        results.write_text(results.read_text()[:-20] + '\n')
    elif damage == 'unknown_key':
        value = json.loads(results.read_text())
        value[SENTINEL] = 1
        results.write_text(json.dumps(value) + '\n')
    elif damage == 'missing_results':
        results.unlink()
    code, out = run(capfd, '--before', good, '--after', bad)
    expected = 'RESULT_UNAVAILABLE' if damage == 'missing_results' else 'RESULT_INVALID'
    assert (code, out) == (2, f'ERROR {expected}\n')


@pytest.mark.parametrize('argv', [[], ['--before'], ['--before', 'x'], ['--after', 'x'],
                                  ['--before', 'x', '--after', 'y', f'--{SENTINEL}']])
def test_argument_errors_are_static(capfd, argv):
    code, out = run(capfd, *argv)
    assert (code, out) == (2, 'ERROR ARGUMENT_ERROR\n')


def test_tracked_repository_location_is_rejected(tmp_path, capfd):
    good = write(tmp_path / 'good', [row('1.pdf', [item('own', 'clean')])])
    code, out = run(capfd, '--before', good, '--after', REPOSITORY / 'engine_v2')
    assert (code, out) == (2, 'ERROR LOCATION_REJECTED\n')


def test_output_is_value_free_and_inputs_are_unchanged(tmp_path, capfd):
    rows = [row(f'{SENTINEL}/가상서류.pdf', [item('own', 'clean')])]
    before, after = write(tmp_path / f'b{SENTINEL}', rows), write(tmp_path / f'a{SENTINEL}', rows)
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for d in (before, after) for p in d.iterdir()}
    code, out = run(capfd, '--before', before, '--after', after)
    assert code == 0
    assert SENTINEL not in out and str(tmp_path) not in out and '가상' not in out and '.pdf' not in out
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for d in (before, after) for p in d.iterdir()} == snapshot
    assert sorted(p.name for p in before.iterdir()) == ['results.jsonl', 'run.json']
    tokens = {token for line in out.splitlines() for token in line.split()}
    allowed = (set(batch.KINDS) | set(tool._field_codes().values()) | set(baseline.ENGINES) |
               set(baseline.VARIANTS) | set(baseline.EXCLUSIONS) |
               {'NA', 'SAME', 'DIFFERENT', 'OCR_BASELINE_COMPARE', 'STATUS', 'key', 'value', 'ROOT_DIGEST',
                'ENGINES', 'VARIANTS', 'COHORT', 'unit', 'before', 'after', 'common', 'before_only', 'after_only',
                'DOCUMENTS', 'PAGES', 'MEASUREMENTS', 'TYPE_CHANGED_PAGES', 'EXCLUSION', 'code', 'GRID', 'cells',
                'measured_cells', 'FIELD', 'GROUP', 'RECOGNITION', 'TIME', 'PAGE_CER_MEAN', 'POOLED_CER',
                'WORD_F1', 'OCR_TIME_PER_PAGE_S', 'TOTAL_TIME_PER_PAGE_S', 'type', 'field', 'engine', 'variant',
                'metric'} | set(tool.FIELD_HEADER.split()) | set(tool.RECOGNITION_HEADER.split()) |
               set(tool.TIME_HEADER.split()))
    for token in tokens - allowed:
        float(token)


def test_module_entry_point_help_is_static():
    env = dict(os.environ, PYTHONPATH=str(REPOSITORY), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', '-m', 'engine_v2.tools.ocr_baseline_compare', '--help'],
                            cwd=REPOSITORY, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and result.stderr == ''
    assert result.stdout.startswith('usage: ocr_baseline_compare')
    assert '--before' in result.stdout and '--after' in result.stdout
