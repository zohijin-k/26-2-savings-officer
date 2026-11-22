"""Print immutable source identity; keep CI ownership separate from CAS PR checks."""
import json, os, subprocess

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

lane = os.environ['CI_LANE']
original = os.environ['CAS_ORIGINAL_SHA']
candidate = os.environ['CAS_CANDIDATE_SHA']
latest_main = None
if lane == 'candidate-main':
    latest_main = git('rev-parse', 'HEAD')
    git('fetch', '--no-tags', 'origin', candidate)
    git('config', 'user.name', 'Synthetic integration verification')
    git('config', 'user.email', 'verification@users.noreply.github.com')
    git('-c', 'core.hooksPath=/dev/null', 'merge', '--no-ff', '--no-edit', candidate)
if lane != 'event':
    git('merge-base', '--is-ancestor', original, candidate)
    git('merge-base', '--is-ancestor', candidate, 'HEAD')
    if lane == 'contract-candidate' and git('rev-parse', 'HEAD') != candidate:
        raise SystemExit('Candidate source SHA mismatch')
else:
    if git('rev-parse', 'HEAD') != os.environ['CI_EVENT_MERGE']:
        raise SystemExit('Event merge SHA mismatch')
source = {'lane': lane, 'event': os.environ['CI_EVENT'], 'pr': os.environ['CI_PR_NUMBER'],
          'event_head': os.environ['CI_EVENT_HEAD'], 'event_base': os.environ['CI_EVENT_BASE'],
          'event_merge': os.environ['CI_EVENT_MERGE'], 'candidate': candidate,
          'original_cas': original, 'latest_main': latest_main,
          'tested_head': git('rev-parse', 'HEAD'), 'tested_tree': git('rev-parse', 'HEAD^{tree}'),
          'tested_parents': git('show', '-s', '--format=%P', 'HEAD').split()}
print('SOURCE_PROVENANCE=' + json.dumps(source, sort_keys=True), flush=True)
print('VERIFIED_SOURCE_SHA=' + source['tested_head'], flush=True)
