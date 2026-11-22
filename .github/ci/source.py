"""Bind each CI lane to the event HEAD or an explicitly recorded merge tree."""
import json
import os
import re
import subprocess
from pathlib import Path


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def sha(name):
    value = os.environ[name]
    if not re.fullmatch(r'[0-9a-f]{40}', value):
        raise SystemExit('Invalid immutable SHA: ' + name)
    return value


lane = os.environ['CI_LANE']
if lane not in ('event', 'pr-head', 'latest-main'):
    raise SystemExit('Unknown lane')
head = sha('CI_EVENT_HEAD')
event_merge = sha('CI_EVENT_MERGE')
subject_head = sha('CI_SUBJECT_HEAD')
expected_checkout = event_merge if lane == 'event' else subject_head
if git('rev-parse', 'HEAD') != expected_checkout:
    raise SystemExit('Checkout SHA does not match event identity')
latest_main = None
if lane == 'latest-main':
    git('fetch', '--no-tags', 'origin', 'refs/heads/main')
    latest_main = git('rev-parse', 'FETCH_HEAD')
    # A conflict fails the job; no commit, deployment, hook, or migration runs here.
    tree = git('merge-tree', '--write-tree', latest_main, subject_head).splitlines()[0]
    if not re.fullmatch(r'[0-9a-f]{40}', tree):
        raise SystemExit('Invalid merge tree')
    git('read-tree', '--reset', '-u', tree)
else:
    tree = git('rev-parse', 'HEAD^{tree}')
if git('write-tree') != tree or git('diff-files', '--name-only'):
    raise SystemExit('Tested files differ from recorded tree')
source = {
    'lane': lane, 'event': os.environ['CI_EVENT'],
    'pr': os.environ.get('CI_PR_NUMBER', ''),
    'event_head': head, 'event_base': os.environ.get('CI_EVENT_BASE', ''),
    'subject_head': subject_head, 'subject_branch': os.environ.get('CI_SUBJECT_BRANCH', ''),
    'event_merge': event_merge, 'latest_main': latest_main,
    'tested_commit': None if lane == 'latest-main' else expected_checkout,
    'tested_tree': tree,
    'integration_parents': [latest_main, subject_head] if latest_main else [],
    'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
    'workflow_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
    'check_owner_sha': event_merge,
}
Path('source-provenance.json').write_text(json.dumps(source, indent=2) + '\n')
print('SOURCE_PROVENANCE=' + json.dumps(source, sort_keys=True), flush=True)
print('VERIFIED_SOURCE_TREE=' + tree, flush=True)
summary = os.environ.get('GITHUB_STEP_SUMMARY')
if summary:
    with open(summary, 'a') as handle:
        handle.write('```json\n' + json.dumps(source, indent=2) + '\n```\n')
