"""``run --only``: only the named diagnostics run; the rest stay empty and print SKIPPED (synthetic only)."""
import inspect
import json
import re

import pytest

from engine_v2.tools import classify_recovery_diag as tool
from engine_v2.tests.test_classify_recovery_diag import SENTINEL, build, fake_ocr, rows  # noqa: F401

#: Row keys each diagnostic fills (left at the blank value when skipped).
ROW_KEYS = dict(G1=('g1', 'g1_decision'), PAYMENT=('payment', 'p1'), A4=('a4',), S3=('s3',), S4=('s4',),
                S2=('s2',), D6=('early', 'billing'), G4=('g4',), T3=('t3',), D11=('d11',))


def _titles(summary):
    return {line.split(' ', 1)[0] for line in summary.splitlines()}


def test_diagnostic_names_follow_the_process_loop():
    loop = re.findall(r"\('([A-Z0-9]+)', (?:True|row|any)", inspect.getsource(tool.process))
    assert loop == list(tool.DIAGNOSTICS)


@pytest.mark.parametrize('text, expected', [('D10,D11,T3', ['T3', 'D10', 'D11']), (' T3 , G1', ['G1', 'T3']),
                                            ('T3,T3', ['T3'])])
def test_only_is_parsed_into_run_order(text, expected):
    assert tool.parse_only(text) == expected


@pytest.mark.parametrize('text', ['', 'T3,', 'T3,NOPE', 't3', SENTINEL])
def test_unknown_names_stop_before_the_run_starts(tmp_path, capsys, text):
    root = tmp_path / 'root'
    root.mkdir()
    out = tmp_path / 'out'
    assert tool.main(['run', '--root', str(root), '--out', str(out), '--only', text]) == 2
    printed = capsys.readouterr().out
    assert printed.strip() == 'ERROR UNKNOWN_DIAGNOSTIC' and not out.exists()
    with pytest.raises(tool.ToolError, match='UNKNOWN_DIAGNOSTIC'):
        tool.run(root, out, only=[text])
    assert not out.exists()


def test_only_runs_the_named_diagnostics_and_marks_the_rest_skipped(tmp_path, fake_ocr):  # noqa: F811
    root = tmp_path / 'root'
    root.mkdir()
    build(root / 'a.pdf', 'plain')
    full, part = tmp_path / 'full', tmp_path / 'part'
    assert tool.run(root, full) == 0
    assert tool.run(root, part, only=['T3', 'D11']) == 0
    (whole,), (row,) = rows(full), rows(part)
    assert row['form'] == whole['form'] == 'NHIS_PAYMENT' and row['decision'] == whole['decision']
    assert row['shadow_errors'] == [] and row['t3'] == whole['t3'] and row['d11'] == whole['d11']
    blank = tool.blank_row(row['key'])
    for name, keys in ROW_KEYS.items():
        for key in keys:
            if name in ('T3', 'D11'):
                assert row[key] is not None
            else:
                assert row[key] == blank[key], key
    meta = json.loads((part / 'run.json').read_text())
    assert meta['options']['only'] == ['T3', 'D11'] and meta['options']['diagnostics'] == ['T3', 'D11']
    full_meta = json.loads((full / 'run.json').read_text())
    assert full_meta['options']['only'] is None and full_meta['options']['diagnostics'] == list(tool.DIAGNOSTICS)

    summary, full_summary = (part / 'summary.txt').read_text(), (full / 'summary.txt').read_text()
    assert 'SKIPPED' not in full_summary
    # Every title a diagnostic owns appears in a full run, so SKIPPED replaces real lines.
    owned = {title for titles in tool.DIAGNOSTICS.values() for title in titles}
    assert owned <= _titles(full_summary)
    lines = summary.splitlines()
    for name, titles in tool.DIAGNOSTICS.items():
        for title in titles:
            mine = [line for line in lines if line.split(' ', 1)[0] == title]
            if name in ('T3', 'D11'):
                assert mine and f'{title} SKIPPED' not in mine
            else:
                assert mine == [f'{title} SKIPPED']
    assert any(line.startswith('T3 ') and line.endswith(' O') for line in lines)  # T3 applied in production
    # Lines outside the diagnostics (the production read) are the same in both runs.
    assert [line for line in lines if line.split(' ', 1)[0] not in owned] == \
        [line for line in full_summary.splitlines() if line.split(' ', 1)[0] not in owned]
