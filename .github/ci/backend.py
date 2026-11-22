"""Run repository-owned critical synthetic tests; never silently skip CAS."""
from pathlib import Path
import os, subprocess, sys
root = Path.cwd()
shared = ["db_write_failures", "db_write_transactions", "submitted_document_immutability", "applicant_telemetry_privacy", "resident_number_privacy"]
names = shared + (['security_access', 'generic_access', 'generic_officer', 'generic_submitted_documents', 'auto_upload_policy'] if (root / 'demo/backend/api/generic_officer.py').exists() else ['access_control', 'officer_forms_access', 'auto_upload_rejection', 'applicant_submission_policy'])
revision = root / 'demo/backend/tests/test_review_revision.py'
if os.environ.get('REQUIRE_CAS') == 'true' and not revision.is_file():
    raise SystemExit('Pinned CAS target is missing required regression tests')
if revision.is_file(): names += ['review_revision']
paths = [f'demo/backend/tests/test_{name}.py' for name in names]
for path in paths:
    if not (root / path).is_file(): raise SystemExit(f'Required test missing: {path}')
print('VERIFIED_SOURCE_SHA=' + subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), flush=True)
raise SystemExit(subprocess.call([sys.executable, '-B', '-m', 'pytest', '-q', *paths, '--basetemp=' + os.environ['CI_SYNTHETIC_ROOT'] + '/pytest']))
