"""Catchable failure and cancellation contracts on synthetic SQLite/storage."""
import asyncio
from hashlib import sha256
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session, create_engine

from demo.backend import models
from demo.backend.api import applications, common, documents, forms
from demo.backend.main import app
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_check import CheckResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_portal_uploads import client


def snapshot():
    with models.engine.connect() as connection:
        rows = {table.name: [dict(row) for row in connection.execute(
            table.select().order_by(*table.primary_key.columns)).mappings()]
            for table in models.SQLModel.metadata.sorted_tables}
    files = {str(p.relative_to(common.STORAGE)): sha256(p.read_bytes()).hexdigest()
             for p in common.STORAGE.rglob('*') if p.is_file()}
    return rows, files


def seed(client, monkeypatch):
    response = client.post('/api/applications', json={'program_code': 'double_savings'})
    assert response.status_code == 200
    aid = response.json()['id']
    path = common.STORAGE / 'documents' / 'synthetic-old.pdf'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'SYNTHETIC OLD ORIGINAL')
    with models.get_session() as session:
        row = models.Document(application_id=aid, slot_key='resident_abstract',
            file_path=str(path.relative_to(common.STORAGE.parent)), file_format='pdf',
            stage1_status='FAIL', findings_json=[{'code': 'LOW_IMAGE_QUALITY', 'severity': 'FAIL'}])
        session.add(row)
        session.add(models.Review(application_id=aid, final_status='NEEDS_REVIEW', officer_memo='synthetic memo'))
        session.commit(); session.refresh(row)
        did = row.id
    monkeypatch.setattr(documents, 'assess_upload', lambda *a, **k: (
        OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT), CheckResult(status='NEEDS_REVIEW', findings=[])))
    return aid, did, path


def upload(client, aid):
    return client.post(f'/api/applications/{aid}/documents', data={'slot_key': 'resident_abstract'},
                       files={'file': ('synthetic.pdf', b'SYNTHETIC NEW', 'application/pdf')})


@pytest.mark.parametrize('action', ['upload', 'delete'])
def test_outer_commit_failure_restores_all_tables_reviews_and_originals(client, monkeypatch, action):
    aid, did, original = seed(client, monkeypatch)
    before = snapshot()
    def fail(connection):
        error = sqlite3.OperationalError('synthetic private database path')
        error.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise OperationalError('private SQL', {}, error)
    event.listen(models.engine, 'commit', fail)
    try:
        response = upload(client, aid) if action == 'upload' else client.delete(f'/api/applications/{aid}/documents/{did}')
    finally:
        event.remove(models.engine, 'commit', fail)
    assert response.status_code == 503
    assert response.headers['retry-after'] == '1'
    assert 'private' not in response.text and str(models.engine.url.database) not in response.text
    assert snapshot() == before
    assert original.read_bytes() == b'SYNTHETIC OLD ORIGINAL'
    assert upload(client, aid).status_code == 200


@pytest.mark.parametrize('failure', ['ocr', 'after_replace_flush'])
def test_upload_exception_preserves_existing_evidence_and_releases_lock(client, monkeypatch, failure):
    aid, did, original = seed(client, monkeypatch)
    before = snapshot()
    if failure == 'ocr':
        def fail(*a, **kw): raise RuntimeError('synthetic OCR error')
        monkeypatch.setattr(documents, 'assess_upload', fail)
    else:
        real_commit = Session.commit
        def fail(session):
            real_commit(session)
            raise RuntimeError('synthetic exception after ORM flush')
        monkeypatch.setattr(Session, 'commit', fail)
    with pytest.raises(RuntimeError, match='synthetic'):
        upload(client, aid)
    assert snapshot() == before
    assert models._session_bind.get() is None


def test_cancelled_http_upload_waiting_for_database_has_no_late_mutation(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch)
    before = snapshot()
    async def exercise():
        attempted = asyncio.Event()
        def seen(conn, cursor, statement, parameters, context, executemany):
            if statement == 'BEGIN IMMEDIATE': attempted.set()
        with models.engine.connect() as holder:
            holder.exec_driver_sql('BEGIN IMMEDIATE')
            event.listen(models.engine, 'before_cursor_execute', seen)
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                        base_url='http://testserver', cookies=dict(client.cookies)) as requester:
                    task = asyncio.create_task(requester.post(f'/api/applications/{aid}/documents',
                        data={'slot_key': 'resident_abstract'},
                        files={'file': ('synthetic.pdf', b'SYNTHETIC CANCELLED', 'application/pdf')}))
                    await asyncio.wait_for(attempted.wait(), 5)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError): await task
            finally:
                event.remove(models.engine, 'before_cursor_execute', seen)
                holder.rollback()
        assert models._session_bind.get() is None
    asyncio.run(exercise())
    assert snapshot() == before
    assert upload(client, aid).status_code == 200


def test_flush_failure_keeps_writer_until_generated_file_restore(client, monkeypatch, tmp_path):
    aid, _, _ = seed(client, monkeypatch)
    with models.get_session() as session:
        duplicate_no = session.get(models.Application, aid).application_no
    target = common.STORAGE / 'synthetic-generated.png'
    target.write_bytes(b'OLD GENERATED')
    original_write = Path.write_bytes
    attempts = []
    def observe(path, content):
        if path == target and content == b'OLD GENERATED':
            with sqlite3.connect(models.engine.url.database, timeout=0) as other:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    other.execute('BEGIN IMMEDIATE')
            attempts.append(True)
        return original_write(path, content)
    monkeypatch.setattr(Path, 'write_bytes', observe)
    with pytest.raises(IntegrityError):
        with models.session_transaction():
            models.preserve_file_on_rollback(target)
            target.write_bytes(b'NEW GENERATED')
            with models.get_session() as session:
                session.add(models.Application(application_no=duplicate_no, program_code='double_savings'))
                session.commit()
    assert attempts == [True] and target.read_bytes() == b'OLD GENERATED'
    with models.session_transaction(): pass


def test_unavailable_database_is_sanitized_and_not_business_conflict(client, monkeypatch, tmp_path):
    broken = create_engine(f'sqlite:///{tmp_path / "missing-parent" / "private.db"}')
    monkeypatch.setattr(models, 'engine', broken)
    try:
        with pytest.raises(HTTPException) as error:
            with models.session_transaction(): pass
        assert error.value.status_code == 503
        assert error.value.headers is None  # Permanent/unclassified DB fault has no automatic retry promise.
        assert 'private' not in error.value.detail and str(tmp_path) not in error.value.detail
        assert models._session_bind.get() is None
    finally:
        broken.dispose()


def test_unsupported_database_does_not_silently_skip_locking(client, monkeypatch):
    monkeypatch.setattr(models, 'engine', SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))
    with pytest.raises(HTTPException) as error:
        with models.session_transaction(): pytest.fail('unlocked write')
    assert error.value.status_code == 503


def test_changed_draft_inputs_during_ocr_conflict_without_saving_stale_verdict(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch)
    real = documents.assess_upload
    def changed(*args, **kwargs):
        result = real(*args, **kwargs)
        # Models a separate instance committing a changed identity/context while
        # this upload has only prepared OCR and does not reserve the DB writer.
        with models.get_session() as session:
            saved = session.get(models.Application, aid)
            saved.identity_json = {'synthetic': 'new identity'}
            session.add(saved); session.commit()
        return result
    monkeypatch.setattr(documents, 'assess_upload', changed)
    response = upload(client, aid)
    assert response.status_code == 409
    assert original.read_bytes() == b'SYNTHETIC OLD ORIGINAL'
    with models.get_session() as session:
        assert session.get(models.Document, did).stage1_status == 'FAIL'
        assert session.get(models.Application, aid).status == 'draft'
        assert session.get(models.Review, 1).final_status == 'NEEDS_REVIEW'


@pytest.mark.parametrize('action', ['upload', 'delete'])
def test_generated_signature_originals_restored_if_outer_commit_fails(client, monkeypatch, action):
    aid, _, _ = seed(client, monkeypatch)
    monkeypatch.setattr(forms, 'STORAGE', common.STORAGE)
    monkeypatch.setattr(forms, 'process_signature_scan', lambda raw: b'NEW PROCESSED')
    with models.get_session() as session:
        number = session.get(models.Application, aid).application_no
    original_base, processed = forms.signature_scan_paths(common.STORAGE, number)
    original_base.parent.mkdir(parents=True, exist_ok=True)
    original_base.with_suffix('.jpg').write_bytes(b'OLD RAW')
    processed.write_bytes(b'OLD PROCESSED')
    before = snapshot()
    def fail(connection): raise RuntimeError('synthetic commit failure')
    event.listen(models.engine, 'commit', fail)
    try:
        with pytest.raises(RuntimeError, match='synthetic commit failure'):
            if action == 'upload':
                client.post(f'/api/applications/{aid}/forms/signature-scan',
                    files={'file': ('synthetic.png', b'NEW RAW', 'image/png')})
            else:
                client.delete(f'/api/applications/{aid}/forms/signature-scan')
    finally:
        event.remove(models.engine, 'commit', fail)
    assert snapshot() == before


def test_submit_commit_failure_restores_prior_archive_and_all_review_state(client, monkeypatch):
    from demo.backend.api import review
    aid, _, _ = seed(client, monkeypatch)
    monkeypatch.setattr(forms, 'STORAGE', common.STORAGE)
    monkeypatch.setattr(forms, '_written_pdf_bytes', lambda row: (b'NEW SYNTHETIC ARCHIVE', 1))
    monkeypatch.setattr(review, '_blockers', lambda row: [])
    monkeypatch.setattr(review, '_run_review', lambda row: models.Review(application_id=aid, final_status='NEEDS_REVIEW'))
    with models.get_session() as session:
        number = session.get(models.Application, aid).application_no
    target = common.STORAGE / 'forms_exports' / f'{number}.pdf'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'OLD SYNTHETIC ARCHIVE')
    before = snapshot()
    def fail(connection): raise RuntimeError('synthetic submit commit failure')
    event.listen(models.engine, 'commit', fail)
    try:
        with pytest.raises(RuntimeError, match='synthetic submit commit failure'):
            client.post(f'/api/applications/{aid}/submit')
    finally:
        event.remove(models.engine, 'commit', fail)
    assert snapshot() == before


def test_delete_commit_failure_restores_original_before_writer_release(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch)
    before = snapshot()
    real_rename = Path.rename
    restored_while_reserved = []
    def observe(path, target):
        if path != original and Path(target) == original:
            # A different connection must still be unable to become a writer
            # while rollback restores the staged document to its original name.
            with sqlite3.connect(models.engine.url.database, timeout=0) as contender:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    contender.execute('BEGIN IMMEDIATE')
            restored_while_reserved.append(True)
        return real_rename(path, target)
    monkeypatch.setattr(Path, 'rename', observe)
    def fail(connection):
        raise RuntimeError('synthetic delete commit failure')
    event.listen(models.engine, 'commit', fail)
    try:
        with pytest.raises(RuntimeError, match='synthetic delete commit failure'):
            client.delete(f'/api/applications/{aid}/documents/{did}')
    finally:
        event.remove(models.engine, 'commit', fail)
    assert restored_while_reserved == [True]
    assert snapshot() == before
    assert original.read_bytes() == b'SYNTHETIC OLD ORIGINAL'
    response = client.delete(f'/api/applications/{aid}/documents/{did}')
    assert response.status_code == 200, response.text
    assert not original.exists()
    with models.get_session() as session:
        assert session.get(models.Document, did) is None
        assert session.get(models.Application, aid).status == 'draft'
        assert session.get(models.Review, 1).final_status == 'NEEDS_REVIEW'


def test_async_timeout_setting_is_restored_before_return_to_pool(client):
    with models.engine.connect() as connection:
        previous = connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one()
    async def transaction():
        async with models.async_session_transaction():
            with models.get_session() as session:
                assert session.connection().exec_driver_sql('PRAGMA busy_timeout').scalar_one() == 0
    asyncio.run(transaction())
    with models.engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one() == previous
