"""Synthetic regressions; no backend service, credentials, originals or OCR."""
import ast
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

from tools.legacy_audit.core import Application, Document, Requirement, VersionProof, classify, summarize
from tools.legacy_audit.policy import REPOSITORY, requirements
from tools.legacy_audit.sqlite_reader import FixtureError, audit, digest, readonly_connection
from tools.legacy_audit.synthetic import AFTER, BEFORE, CANARY, SCENARIOS, SUBMITTED, create_fixture, seal


def base():
    return Application(1, SUBMITTED, (Document(1, 'proof', 'PASS', BEFORE, 'present', False, 'TYPE'),),
                       ('PASS',), (Requirement('proof', ('TYPE',)),),
                       (VersionProof(1, 'a'*64, 'a'*64, True),))


def codes(result):
    return {f.code for f in result.findings}


@pytest.mark.parametrize('slot,verdict,grade', [
    ('proof', 'PASS', 'NO_FLAG_FOUND'), ('auto','PASS','HIGH'), ('unassigned','PASS','HIGH'),
    ('auto','NEEDS_REVIEW','REVIEW_REQUIRED'), ('auto','FAIL','REVIEW_REQUIRED'),
    (' AUTO ', 'PASS', 'HIGH'), ('', 'PASS', 'HIGH')])
def test_document_pass_is_not_aggregate_pass(slot, verdict, grade):
    app = base()
    result = classify(replace(app, review_statuses=(verdict,), documents=(replace(app.documents[0], slot=slot),)))
    assert result.grade == grade
    assert ('LEGACY_WITH_AGGREGATE_PASS' in codes(result)) == (verdict == 'PASS' and slot != 'proof')


@pytest.mark.parametrize('name,grade,code', [
    ('normal','NO_FLAG_FOUND',None), ('auto_pass','HIGH','LEGACY_WITH_AGGREGATE_PASS'),
    ('unassigned_pass','HIGH','DOCUMENT_UNASSIGNED'), ('auto_review','REVIEW_REQUIRED','LEGACY_AUTO_OR_UNASSIGNED'),
    ('auto_fail','REVIEW_REQUIRED','LEGACY_AUTO_OR_UNASSIGNED'), ('missing_required_pass','HIGH','REQUIRED_SLOT_MISSING'),
    ('proven_change','CRITICAL','POST_SUBMISSION_ORIGINAL_CHANGE_PROVEN'),
    ('suspected_change','REVIEW_REQUIRED','POST_SUBMISSION_UPLOAD_SUSPECTED'),
    ('no_history','UNKNOWN','HISTORICAL_ORIGINAL_UNVERIFIABLE'),
    ('missing_file','HIGH','FILE_MISSING_OR_REFERENCE_INVALID'), ('multiple_flags','HIGH','POST_SUBMISSION_UPLOAD_SUSPECTED'),
    ('generic_independent','NO_FLAG_FOUND',None), ('normal_memo','NO_FLAG_FOUND',None),
    ('normal_rereview','NO_FLAG_FOUND',None), ('merged_assigned_pass','HIGH','LEGACY_WITH_AGGREGATE_PASS'),
    ('no_review','UNKNOWN','REVIEW_HISTORY_MISSING')])
def test_required_synthetic_scenarios(fixture_root, name, grade, code):
    _, results = audit(fixture_root)
    result = results[SCENARIOS.index(name)]
    assert result.grade == grade
    if code:
        assert code in codes(result)
    if name == 'multiple_flags':
        assert {'LEGACY_WITH_AGGREGATE_PASS','FILE_MISSING_OR_REFERENCE_INVALID',
                'HISTORICAL_ORIGINAL_UNVERIFIABLE'}.issubset(codes(result))
    if name == 'suspected_change':
        assert 'POST_SUBMISSION_ORIGINAL_CHANGE_PROVEN' not in codes(result)


@pytest.fixture(scope='module')
def fixture_root():
    return create_fixture()


def full_snapshot(root):
    with sqlite3.connect((root/'synthetic.sqlite3').as_uri()+'?mode=ro', uri=True) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        contents = {t:sorted((list(r) for r in conn.execute('SELECT * FROM "'+t+'"')), key=repr) for t in tables}
    files = {str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
    return {'counts':{t:len(v) for t,v in contents.items()},
            'logical_sha256':sha256(json.dumps(contents,sort_keys=True).encode()).hexdigest(),
            'contents': contents, 'files':files}


def test_repeated_audit_all_tables_and_files_unchanged(fixture_root):
    before = full_snapshot(fixture_root)
    first = audit(fixture_root)
    second = audit(fixture_root)
    after = full_snapshot(fixture_root)
    assert first == second
    assert before == after
    summary = first[0]
    assert sum(summary['grades'].values()) == len(SCENARIOS)
    assert summary['legacy_with_aggregate_pass'] == 4
    assert summary['proven_post_submission_change'] == 1
    assert summary['review_required_applications'] < sum(summary['signals_by_application'].values())


@pytest.mark.parametrize('sql', ['INSERT INTO application (id) VALUES (9999)',
    "UPDATE application SET status='decided'", 'DELETE FROM document', 'CREATE TABLE forbidden(x)',
    'ALTER TABLE document ADD COLUMN forbidden TEXT', 'DROP TABLE review',
    'PRAGMA user_version=99', "ATTACH DATABASE ':memory:' AS forbidden", 'VACUUM', 'BEGIN IMMEDIATE'])
def test_sqlite_denies_mutation(fixture_root, sql):
    before = full_snapshot(fixture_root)
    with readonly_connection(fixture_root) as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(sql)
    assert full_snapshot(fixture_root) == before


def test_default_output_privacy_and_no_backend_imports(fixture_root):
    code = """import json, sys, socket
from pathlib import Path
def blocked(*args, **kwargs): raise RuntimeError('NETWORK_BLOCKED')
socket.socket.connect = blocked
socket.create_connection = blocked
from tools.legacy_audit.sqlite_reader import audit
result, _ = audit(Path(sys.argv[1]))
assert not any(n == 'demo.backend.models' or n.startswith(('sqlmodel','sqlalchemy','demo.backend.api','demo.backend.ocr','engine_v2')) for n in sys.modules)
print(json.dumps(result, sort_keys=True))
"""
    done = subprocess.run([sys.executable,'-B','-c',code,str(fixture_root)], capture_output=True,text=True)
    assert done.returncode == 0, done.stderr
    assert CANARY not in done.stdout + done.stderr
    assert 'SYNTHETIC-1' not in done.stdout
    assert 'storage/' not in done.stdout
    assert 'application_id' not in done.stdout
    assert 'document_id' not in done.stdout
    assert json.loads(done.stdout)['applications_inspected'] == len(SCENARIOS)


@pytest.mark.parametrize('change', ['raw_db','outside','tamper','symlink','unsealed','wrong_repo','bad_marker'])
def test_fixture_guard_rejects(change, tmp_path):
    root = create_fixture()
    if change == 'raw_db': root = root/'synthetic.sqlite3'
    elif change == 'outside': root = Path.cwd()
    elif change == 'tamper': (root/'storage'/'extra').write_bytes(b'changed')
    elif change == 'symlink':
        link = root.parent/(root.name+'-link')
        link.symlink_to(root, target_is_directory=True)
        root = link
    elif change == 'unsealed': (root/'synthetic.sqlite3-wal').write_bytes(b'synthetic')
    elif change == 'wrong_repo':
        raw=json.loads((root/'fixture.json').read_text());raw['repository']='other';(root/'fixture.json').write_text(json.dumps(raw))
    elif change == 'bad_marker': (root/'fixture.json').write_text('{invalid')
    with pytest.raises(FixtureError): audit(root)


@pytest.mark.parametrize('path', ['/not-allowed/original.pdf','../escape.pdf','storage/absent.pdf','synthetic.sqlite3','scenarios.json'])
def test_invalid_file_references_are_flagged(path):
    root=create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('UPDATE document SET file_path=? WHERE id=1',(path,))
    seal(root)
    _, results=audit(root)
    assert 'FILE_MISSING_OR_REFERENCE_INVALID' in codes(results[0])
    assert results[0].grade != 'NO_FLAG_FOUND'


def test_missing_metadata_is_unknown():
    root=create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('ALTER TABLE document DROP COLUMN uploaded_at')
    seal(root)
    _, results=audit(root)
    assert all('METADATA_INCOMPLETE' in codes(r) for r in results)
    assert all(r.grade != 'NO_FLAG_FOUND' for r in results)


def test_missing_snapshot_cannot_fall_back_to_current_posting():
    if REPOSITORY != 'youth':
        assert requirements('posting_700',{},None,[],{'requirements':[]}) is None
        return
    root=create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('DELETE FROM programapplicationsnapshot')
    seal(root)
    _, results=audit(root)
    assert 'REQUIREMENTS_UNKNOWN' in codes(results[SCENARIOS.index('generic_independent')])


@pytest.mark.parametrize('proof', [VersionProof(1,'a'*64,'b'*64,False),
    VersionProof(99,'a'*64,'b'*64,True),VersionProof(1,'not-a-hash','b'*64,True)])
def test_unverified_hash_or_event_never_proves_change(proof):
    result=classify(replace(base(),proofs=(proof,)))
    assert result.grade == 'UNKNOWN'
    assert 'POST_SUBMISSION_ORIGINAL_CHANGE_PROVEN' not in codes(result)


def test_duplicate_proof_and_timestamp_timezones_are_uncertain():
    app=base()
    result=classify(replace(app,proofs=app.proofs*2,
        documents=(replace(app.documents[0], uploaded_at=AFTER+'+09:00'),)))
    assert {'VERSION_EVIDENCE_AMBIGUOUS','TIMESTAMP_BASIS_UNKNOWN'}.issubset(codes(result))
    assert result.grade == 'UNKNOWN'


def test_historical_pass_is_retained_after_rereview():
    result=classify(replace(base(), review_statuses=('PASS','FAIL'),
                            documents=(replace(base().documents[0],merged=True),)))
    assert result.grade == 'HIGH'


def test_no_history_is_never_no_flag():
    assert classify(replace(base(),proofs=())).grade == 'UNKNOWN'
    assert classify(replace(base(),requirements=None)).grade != 'NO_FLAG_FOUND'
    with pytest.raises(ValueError): summarize((classify(base()),)*2)


def test_policy_conditional_slots_and_bankbook():
    criteria={'subsidy_catalog':[]}
    context={'work_category':'직장가입자','workplace_count':2,'admin_fixed_term':True,
             'paper_forms':{'서식5':True}}
    built=requirements('double_savings',context,criteria,[],None)
    assert {'work_proof_1','work_proof_2','labor_contract','admin_info_consent'}.issubset({r.slot for r in built})
    assert requirements('double_savings',{},criteria,[],None) is None
    job=requirements('job_package',{},criteria,[{'item_type':'photo','count_index':1,'linked_interview_index':None}],None)
    assert {'bank_account','resident_abstract','photo_1_photo','photo_1_receipt'}.issubset({r.slot for r in job})
    assert requirements('job_package',{},None,[],None) is None


def test_runtime_source_imports_are_closed():
    root=Path(__file__).parents[1]
    forbidden=('sqlmodel','sqlalchemy','demo.backend.models','demo.backend.api','demo.backend.ocr','socket','requests','httpx','subprocess')
    for name in ('core.py','policy.py','sqlite_reader.py','__main__.py'):
        tree=ast.parse((root/name).read_text())
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import): modules=[n.name for n in node.names]
            if isinstance(node,ast.ImportFrom): modules=[node.module or '']
            assert not any(m.startswith(forbidden) for m in modules)


def test_missing_application_table_fails_closed():
    root = create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('DROP TABLE application')
    seal(root)
    with pytest.raises(FixtureError):
        audit(root)


def test_independent_version_binding_must_match_submission():
    root = create_fixture()
    path = root/'submission_versions.json'
    versions = json.loads(path.read_text())
    for version in versions:
        version['submitted_at'] = BEFORE
    path.write_text(json.dumps(versions))
    seal(root)
    _, results = audit(root)
    assert all(r.grade != 'CRITICAL' for r in results)
    assert 'VERSION_EVIDENCE_UNVERIFIED' in codes(results[SCENARIOS.index('proven_change')])


def test_orphan_relationships_are_counted_without_ids():
    root = create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('UPDATE document SET application_id=999999 WHERE id=1')
    seal(root)
    summary, _ = audit(root)
    assert summary['orphan_documents'] == 1
    assert summary['collection_review_required'] is True
    assert '999999' not in json.dumps(summary)


def test_symlink_document_is_not_opened():
    root = create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        path = root/conn.execute('SELECT file_path FROM document WHERE id=1').fetchone()[0]
    path.unlink()
    path.symlink_to(root/'scenarios.json')
    # A symlink cannot pass the sealed fixture gate, even with identical bytes.
    seal(root)
    with pytest.raises(FixtureError):
        audit(root)


def test_duplicate_document_and_wrong_type_keep_all_signals():
    app = base()
    result = classify(replace(app, documents=(app.documents[0], replace(app.documents[0], identifier=2, detected_type='WRONG')), proofs=()))
    assert {'DUPLICATE_SLOT','SLOT_TYPE_EVIDENCE_INCOMPLETE','HISTORICAL_ORIGINAL_UNVERIFIABLE',
            'INCOMPLETE_WITH_AGGREGATE_PASS'}.issubset(codes(result))
    assert result.grade == 'HIGH'


def test_cli_rejects_raw_db_without_traceback(fixture_root):
    done = subprocess.run([sys.executable, '-B', '-m', 'tools.legacy_audit', '--fixture',
                           str(fixture_root/'synthetic.sqlite3')], capture_output=True, text=True)
    assert done.returncode == 2
    assert json.loads(done.stdout)['status'] == 'BLOCKED'
    assert done.stderr == ''


def test_snapshot_posting_binding_cannot_be_bypassed():
    if REPOSITORY != 'youth':
        return
    root = create_fixture()
    with sqlite3.connect(root/'synthetic.sqlite3') as conn:
        conn.execute('UPDATE programapplicationsnapshot SET posting_id=701')
    seal(root)
    _, results = audit(root)
    assert 'REQUIREMENTS_UNKNOWN' in codes(results[SCENARIOS.index('generic_independent')])


def test_fixture_schema_matches_actual_repository_model(fixture_root):
    from demo.backend import models
    with sqlite3.connect(fixture_root/'synthetic.sqlite3') as conn:
        for table in models.SQLModel.metadata.sorted_tables:
            actual = {r[1] for r in conn.execute('PRAGMA table_info("'+table.name+'")')}
            assert actual == set(table.columns.keys())
    assert 'updated_at' not in models.Document.model_fields
    assert not any('hash' in name or 'version' in name for name in models.Document.model_fields)


def test_generic_optional_documents_preserve_all_document_contract():
    app = base()
    result = classify(replace(app, requirements=(Requirement('proof', required=False),),
        documents=(replace(app.documents[0], status='FAIL'),), all_documents_must_pass=True))
    assert result.grade == 'HIGH'
    assert 'GENERIC_DOCUMENT_NOT_PASS' in codes(result)
