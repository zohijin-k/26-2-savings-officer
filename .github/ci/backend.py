"""Run repository-owned critical synthetic tests; never silently skip CAS."""
from pathlib import Path
import os, subprocess, sys
root = Path.cwd()
shared = ["db_write_failures", "db_write_transactions", "submitted_document_immutability", "applicant_telemetry_privacy", "resident_number_privacy", "common_ocr_parity", "ocr_resource_guard", "ocr_gate", "image_quality_page_box", "ocr_png_encoding"]
names = shared + (['security_access', 'generic_access', 'generic_officer', 'generic_submitted_documents', 'auto_upload_policy', 'ocr_gate_bypass'] if (root / 'demo/backend/api/generic_officer.py').exists() else ['access_control', 'officer_forms_access', 'auto_upload_rejection', 'applicant_submission_policy'])
revision = root / 'demo/backend/tests/test_review_revision.py'
if os.environ.get('REQUIRE_CAS') == 'true' and not revision.is_file():
    raise SystemExit('CAS PR source is missing required regression tests')
if revision.is_file():
    contract = root / 'demo/backend/tests/test_review_bulk_revision_contract.py'
    if not contract.is_file(): raise SystemExit('CAS source lacks bulk 422 contract correction')
    names += ['review_revision', 'review_bulk_revision_contract']
    if not (root / 'demo/backend/tests/test_review_write_guard.py').is_file(): raise SystemExit('CAS source lacks mixed-writer SQLite guard tests')
    names += ['review_write_guard', 'integrity_closure']
paths = [f'demo/backend/tests/test_{name}.py' for name in names]
for path in paths:
    if not (root / path).is_file(): raise SystemExit(f'Required test missing: {path}')
if revision.is_file(): paths += [str(Path(__file__).resolve().with_name('test_bulk_contract.py'))]
print('VERIFIED_SOURCE_TREE=' + subprocess.check_output(['git', 'write-tree'], text=True).strip(), flush=True)
raise SystemExit(subprocess.call([sys.executable, '-B', '-m', 'pytest', '-q', *paths, '--basetemp=' + os.environ['CI_SYNTHETIC_ROOT'] + '/pytest']))
