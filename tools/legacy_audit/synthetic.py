"""Explicit synthetic fixture writer. Never imported by the audit CLI/reader.

Uses repository columns and foreign keys in a newly created private temporary root.
Review cardinality represents a pre-CAS snapshot, including historical duplicates;
production metadata and its current uniqueness constraint remain unchanged.
Never calls init_db, get_session, default criteria, or the default DB engine.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .policy import REPOSITORY, requirements
from .sqlite_reader import digest

SUBMITTED = '2026-11-20T12:00:00'
BEFORE = '2026-11-20T11:00:00'
AFTER = '2026-11-20T13:00:00'
CANARY = 'SYNTHETIC_PRIVATE_CANARY_DO_NOT_OUTPUT'
SCENARIOS = ('normal', 'auto_pass', 'unassigned_pass', 'auto_review', 'auto_fail',
             'missing_required_pass', 'proven_change', 'suspected_change', 'no_history',
             'missing_file', 'multiple_flags', 'generic_independent', 'normal_memo',
             'normal_rereview', 'merged_assigned_pass', 'no_review')


def seal(root: Path) -> None:
    manifest = {'kind': 'PHASE4A_GENERATED_SYNTHETIC_V1', 'repository': REPOSITORY,
                'database': 'synthetic.sqlite3', 'files': {
                    str(p.relative_to(root)): digest(p) for p in sorted(root.rglob('*'))
                    if p.is_file() and p.name != 'fixture.json'}}
    (root / 'fixture.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
    for file in root.rglob('*'):
        if file.is_file():
            file.chmod(0o600)


def create_fixture(parent: Path | None = None) -> Path:
    from sqlalchemy import MetaData, UniqueConstraint
    from sqlmodel import SQLModel, create_engine
    from demo.backend import models

    root = Path(tempfile.mkdtemp(prefix='phase4a-synthetic-', dir=parent or '/private/tmp'))
    root.chmod(0o700)
    db = root / 'synthetic.sqlite3'
    engine = create_engine('sqlite:///' + str(db))
    # The read-only auditor must still inspect pre-CAS duplicate Review history.
    # Copy metadata so fixture generation cannot weaken the production schema.
    legacy_metadata = MetaData()
    for table in SQLModel.metadata.sorted_tables:
        table.to_metadata(legacy_metadata)
    review = legacy_metadata.tables['review']
    for constraint in tuple(review.constraints):
        if (isinstance(constraint, UniqueConstraint)
                and tuple(column.name for column in constraint.columns) == ('application_id',)):
            review.constraints.remove(constraint)
    legacy_metadata.create_all(engine)
    engine.dispose()
    versions = []
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE phase4a_fixture (kind TEXT NOT NULL)')
        conn.execute("INSERT INTO phase4a_fixture VALUES ('SYNTHETIC_ONLY')")
        # This extra table exists outside models.py in youth generic_review.py.
        if REPOSITORY == 'youth':
            conn.execute('CREATE TABLE IF NOT EXISTS genericreviewchecks (application_id INTEGER PRIMARY KEY, checks_json JSON NOT NULL, updated_at DATETIME NOT NULL)')
        conn.execute('INSERT INTO programcriteriaversion (program_code,version,criteria_json,changed_at,changed_role) VALUES (?,?,?,?,?)',
                     ('double_savings', 1, json.dumps({'subsidy_catalog': []}), BEFORE, 'synthetic'))
        conn.execute('INSERT INTO programcriteriaversion (program_code,version,criteria_json,changed_at,changed_role) VALUES (?,?,?,?,?)',
                     ('job_package', 1, json.dumps({'subsidy_catalog': []}), BEFORE, 'synthetic'))
        doc_id = 0
        for app_id, scenario in enumerate(SCENARIOS, 1):
            generic = REPOSITORY == 'youth' and scenario == 'generic_independent'
            program = 'posting_700' if generic else 'double_savings'
            context = {'work_category': '직장가입자', 'workplace_count': 1}
            # All personal fields are synthetic canaries; none are needed by the reader.
            fields = {'name': CANARY, 'birth_date': CANARY, 'phone': CANARY, 'address': CANARY}
            conn.execute('INSERT INTO application (id,application_no,program_code,criteria_version,status,form1_json,self_check_json,form5_json,doc_context_json,identity_json,created_at,updated_at,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (app_id, 'SYNTHETIC-' + str(app_id), program, 1, 'submitted', json.dumps(fields), '{}', '{}',
                 json.dumps(context), json.dumps(fields), BEFORE,
                 AFTER if scenario in {'normal_memo','normal_rereview'} else SUBMITTED, SUBMITTED))
            snapshot = {'requirements': [{'slot_key': 'frozen_proof', 'doc_type': 'SYNTHETIC_TYPE', 'required': True}]}
            if generic:
                conn.execute('INSERT INTO programapplicationsnapshot (application_id,posting_id,snapshot_json,created_at) VALUES (?,?,?,?)',
                             (app_id, 700, json.dumps(snapshot), BEFORE))
                conn.execute('INSERT INTO genericreviewchecks VALUES (?,?,?)', (app_id, json.dumps({'memo': CANARY}), AFTER))
                # Deliberately no current ProgramPosting: application snapshot owns requirements.
            reqs = requirements(program, context, {'subsidy_catalog': []}, [], snapshot)
            for req in reqs or ():
                if scenario == 'missing_required_pass' and req == reqs[0]:
                    continue
                doc_id += 1
                relative = f'storage/synthetic-{app_id}-{doc_id}.bin'
                path = root / relative
                path.parent.mkdir(exist_ok=True)
                original = f'SYNTHETIC original {app_id} {doc_id}'.encode()
                path.write_bytes(original)
                if scenario == 'proven_change':
                    path.write_bytes(b'SYNTHETIC independently changed bytes')
                first = req == reqs[0]
                slot = 'auto' if first and scenario in {'auto_pass', 'auto_review', 'auto_fail', 'multiple_flags'} else (
                       'unassigned' if first and scenario == 'unassigned_pass' else req.slot)
                uploaded = AFTER if first and scenario in {'suspected_change', 'multiple_flags'} else BEFORE
                source, page_index = None, None
                if scenario == 'merged_assigned_pass':
                    source = relative
                    page_index = 0
                conn.execute('INSERT INTO document (id,application_id,slot_key,doc_type,expected_doc_type,file_path,file_format,ocr_json,stage1_status,findings_json,page_index,source_file_path,uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (doc_id, app_id, slot, (req.accepted_types or ('SYNTHETIC_TYPE',))[0], (req.accepted_types or ('SYNTHETIC_TYPE',))[0],
                     relative, 'pdf', json.dumps({'text': CANARY, 'fields': fields}), 'PASS', '[]', page_index, source, uploaded))
                if scenario not in {'no_history', 'auto_pass', 'unassigned_pass', 'auto_review', 'auto_fail', 'multiple_flags', 'suspected_change', 'merged_assigned_pass', 'no_review'}:
                    version_path = f'versions/submitted-{doc_id}.bin'
                    version = root / version_path
                    version.parent.mkdir(exist_ok=True)
                    version.write_bytes(original)
                    versions.append({'application_id': app_id, 'document_id': doc_id,
                        'submitted_at': SUBMITTED, 'version_path': version_path,
                        'submitted_sha256': sha256(original).hexdigest(),
                        'binding': 'SYNTHETIC_INDEPENDENT_SUBMISSION_VERSION'})
                if first and scenario in {'missing_file', 'multiple_flags'}:
                    path.unlink()
            if scenario != 'no_review':
                verdicts = ['NEEDS_REVIEW','PASS'] if scenario == 'normal_rereview' else [
                    'NEEDS_REVIEW' if scenario == 'auto_review' else 'FAIL' if scenario == 'auto_fail' else 'PASS']
                for verdict in verdicts:
                    conn.execute('INSERT INTO review (application_id,final_status,score_json,tiebreak_json,review_payload_json,officer_memo,created_at) VALUES (?,?,?,?,?,?,?)',
                                 (app_id, verdict, '{}', '[]', json.dumps({'private': CANARY}), CANARY, AFTER))
    (root / 'submission_versions.json').write_text(json.dumps(versions, indent=2))
    (root / 'scenarios.json').write_text(json.dumps({str(i): name for i, name in enumerate(SCENARIOS, 1)}, indent=2))
    seal(root)
    return root


if __name__ == '__main__':
    print(create_fixture())
