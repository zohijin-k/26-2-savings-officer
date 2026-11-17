"""Value presence (actual_present) in ocr_baseline field records and compare outcomes."""
from copy import deepcopy
import json

import pytest

from engine_v2.tests.test_ocr_baseline import corpus, fake_ocr, invoke, make_pdf, records  # noqa: F401
from engine_v2.tests.test_ocr_baseline_compare import item, row, write
from engine_v2.tools import batch_assess as batch
from engine_v2.tools import ocr_baseline as baseline
from engine_v2.tools import ocr_baseline_compare as compare_tool
from engine_v2.tools import ocr_baseline_fields as fields

SECRET = 'SYNTHETIC_PRESENCE_SECRET_558211'


# ---------------------------------------------------------------- compare_fields


def test_presence_is_opt_in_and_never_changes_the_six_counts():
    reference = {'성명': '가짜이름', '발급일': '2026-11-10', '생년월일': '1990-01-01'}
    observed = {'성명': '가짜이름', '발급일': '2026-11-11'}
    plain = fields.compare_fields('NHIS_PAYMENT', reference, observed, 'NHIS_PAYMENT')
    marked = fields.compare_fields('NHIS_PAYMENT', reference, observed, 'NHIS_PAYMENT', presence=True)
    assert all(set(value) == set(fields.FIELD_COUNTS) for value in plain.values())
    assert {key: {k: v for k, v in value.items() if k != 'actual_present'} for key, value in marked.items()} == plain
    assert marked['성명']['match'] == 1 and marked['성명']['actual_present'] == 1
    assert marked['발급일']['match'] == 0 and marked['발급일']['actual_present'] == 1      # wrong value
    assert marked['생년월일']['match'] == 0 and marked['생년월일']['actual_present'] == 0  # blank
    missing = [key for key, value in marked.items() if value['missing_reference']]
    assert missing and all(marked[key]['actual_present'] == 0 for key in missing)


def test_whitespace_only_observed_value_is_not_present():
    marked = fields.compare_fields('NHIS_PAYMENT', {'성명': '가짜이름'}, {'성명': '  '}, 'NHIS_PAYMENT', presence=True)
    assert marked['성명']['actual_present'] == 0 and marked['성명']['match'] == 0


# ---------------------------------------------------------------- row validation


def _with_presence(measurement, value):
    measurement = deepcopy(measurement)
    for field in measurement['fields'].values():
        field['actual_present'] = value if field['eligible'] else 0
    return measurement


def _meta():
    return baseline.validate_meta(dict(schema_version=baseline.VERSION, root_digest='a' * 64, engines=['own'],
                                       variants=['clean'], settings=deepcopy(baseline.SETTINGS)))


def test_rows_with_and_without_presence_both_validate():
    legacy = row('x/a.pdf', [item('own', 'clean')])
    recorded = row('x/a.pdf', [_with_presence(item('own', 'clean'), 1)])
    assert baseline.validate_row(legacy, _meta()) is legacy
    assert baseline.validate_row(recorded, _meta()) is recorded


@pytest.mark.parametrize('mutate', [
    lambda f: f.update(actual_present=2),
    lambda f: f.update(actual_present=True),
    lambda f: f.update(actual_present=0),                                  # match=1 needs presence
    lambda f: f.update(eligible=0, match=0, missing_reference=1, ocr_cause=0, actual_present=1),
    lambda f: f.update(observed_value=1),
])
def test_invalid_presence_records_are_rejected(mutate):
    recorded = row('x/a.pdf', [_with_presence(item('own', 'clean'), 1)])
    mutate(next(iter(recorded['pages'][0]['measurements'][0]['fields'].values())))
    with pytest.raises(batch.BatchError):
        baseline.validate_row(recorded, _meta())


def test_summary_counts_ignore_presence():
    legacy = [row('x/a.pdf', [item('own', 'clean', match=0)])]
    recorded = [row('x/a.pdf', [_with_presence(item('own', 'clean', match=0), 1)])]
    assert baseline.build_summary(_meta(), legacy) == baseline.build_summary(_meta(), recorded)


def test_cli_records_presence_for_every_field(corpus, monkeypatch, capfd):  # noqa: F811
    root, out = corpus
    source = make_pdf(root / 'neutral.pdf')
    fake_ocr(monkeypatch, source)
    assert invoke(root, out, '--engines', 'own') == 0
    measurement = records(out)[0]['pages'][0]['measurements'][0]
    assert measurement['fields']
    for value in measurement['fields'].values():
        assert set(value) == set(fields.FIELD_COUNTS) | {'actual_present'}
        assert value['actual_present'] >= value['match']
    assert measurement['fields']['성명']['actual_present'] == 1


# ---------------------------------------------------------------- compare outcomes


def test_outcome_classification():
    eligible = dict(eligible=1, match=0, missing_reference=0)
    assert compare_tool.outcome(dict(type_match=1), dict(eligible, match=1)) == 'MATCH'
    assert compare_tool.outcome(dict(type_match=1), dict(eligible, actual_present=0)) == 'BLANK'
    assert compare_tool.outcome(dict(type_match=1), dict(eligible, actual_present=1)) == 'WRONG'
    assert compare_tool.outcome(dict(type_match=0), dict(eligible, actual_present=1)) == 'OTHER'
    assert compare_tool.outcome(dict(type_match=1), dict(eligible)) == 'NA'
    assert compare_tool.outcome(dict(type_match=1), dict(eligible=0, match=0, missing_reference=1)) is None


def _run(capfd, *args):
    code = compare_tool.main([str(a) for a in args])
    captured = capfd.readouterr()
    assert captured.err == ''
    return code, captured.out


def test_outcomes_flag_reports_distribution_and_transitions(tmp_path, capfd):
    name = f'{SECRET}/가상서류.pdf'
    blank = _with_presence(item('own', 'clean', match=0), 0)
    before = write(tmp_path / 'before', [row(name, [item('own', 'clean')])])           # legacy rows
    after = write(tmp_path / 'after', [row(name, [blank]), row(f'{SECRET}/new.pdf', [_with_presence(item('own', 'clean'), 1)])])
    code, default = _run(capfd, '--before', before, '--after', after)
    assert code == 0 and 'OUTCOME' not in default and 'TRANSITION' not in default
    code, out = _run(capfd, '--before', before, '--after', after, '--outcomes')
    assert code == 0 and out.startswith(default)
    codes = compare_tool._field_codes()
    count = len(batch.FIELDS['NHIS_PAYMENT'])
    key = codes['성명']
    assert f'OUTCOME NHIS_PAYMENT {key} own clean BEFORE 1 0 0 0 0' in out
    assert f'OUTCOME NHIS_PAYMENT {key} own clean AFTER 1 1 0 0 0' in out
    assert f'TRANSITION NHIS_PAYMENT {key} own clean MATCH BLANK 1' in out
    assert f'TRANSITION NHIS_PAYMENT {key} own clean ABSENT MATCH 1' in out
    transitions = [line for line in out.splitlines() if line.startswith('TRANSITION NHIS_PAYMENT')]
    assert sum(int(line.split()[-1]) for line in transitions) == 2 * count
    assert SECRET not in out and '가상' not in out and '.pdf' not in out and str(tmp_path) not in out


def test_legacy_rows_on_both_sides_give_na_not_an_error(tmp_path, capfd):
    legacy = [row('x/a.pdf', [item('own', 'clean', match=0)])]
    before, after = write(tmp_path / 'b', legacy), write(tmp_path / 'a', legacy)
    code, out = _run(capfd, '--before', before, '--after', after, '--outcomes')
    key = compare_tool._field_codes()['성명']
    assert code == 0
    assert f'OUTCOME NHIS_PAYMENT {key} own clean BEFORE 0 0 0 0 1' in out
    assert f'TRANSITION NHIS_PAYMENT {key} own clean NA NA 1' in out
    assert json.dumps(out)  # plain text only
