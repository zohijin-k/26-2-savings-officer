"""Resolve a CI PR's CAS subject without trusting a mutable checkout ref."""
import os
import re
import subprocess
from pathlib import Path

head = os.environ['CI_EVENT_HEAD']
branch = ''
if os.environ.get('CI_USE_CAS_BRANCH') == 'true':
    repo = os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise SystemExit('Invalid repository')
    branch = 'feat/phase6d-review-cas'
    ref = 'refs/heads/' + branch
    rows = subprocess.check_output(
        ['git', 'ls-remote', '--exit-code', 'https://github.com/' + repo + '.git', ref],
        text=True,
    ).strip().splitlines()
    if len(rows) != 1 or rows[0].split()[1] != ref:
        raise SystemExit('Ambiguous CAS branch')
    head = rows[0].split()[0]
if not re.fullmatch(r'[0-9a-f]{40}', head):
    raise SystemExit('Invalid immutable subject SHA')
with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
    output.write('head=' + head + '\nbranch=' + branch + '\n')
print('RESOLVED_SUBJECT_HEAD=' + head, flush=True)
print('RESOLVED_SUBJECT_BRANCH=' + branch, flush=True)
