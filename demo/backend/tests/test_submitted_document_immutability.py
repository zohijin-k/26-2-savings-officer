"""Synthetic-only regression for the applicant's submitted document boundary."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import wraps
import hashlib
import threading

import pymupdf
import pytest
from sqlalchemy import select as table_select
from sqlmodel import select

from demo.backend import models
from demo.backend.api import common, documents, forms, review
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.security_support import claim_synthetic_application, authenticate_officer


def pdf(text):
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40, 50), text, fontname="korea")
        return doc.tobytes()


def seed(client, monkeypatch, *, submit=True):
    monkeypatch.setattr(forms, "STORAGE", common.STORAGE)
    app = ready(make_application(premium=1))
    claim_synthetic_application(client, app.id)
    with models.get_session() as session:
        row = session.exec(select(models.Document).where(
            models.Document.application_id == app.id,
            models.Document.slot_key == "resident_abstract")).one()
        target = common.STORAGE / "documents" / app.application_no / "resident_abstract" / "FAKE-original.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf("SYNTHETIC ORIGINAL"))
        row.file_path = str(target.relative_to(common.STORAGE.parent))
        session.add(row)
        session.commit()
        did = row.id
    if submit:
        assert client.get(f"/api/applications/{app.id}/final-check").json()["can_submit"]
        response = client.post(f"/api/applications/{app.id}/submit")
        assert response.status_code == 200, response.text
    return app.id, did, target


def snapshot():
    with models.engine.connect() as connection:
        tables = {table.name: [dict(row) for row in connection.execute(table_select(table)).mappings()]
                  for table in models.SQLModel.metadata.sorted_tables}
    files = {str(path.relative_to(common.STORAGE)): hashlib.sha256(path.read_bytes()).hexdigest()
             if path.is_file() else "DIRECTORY" for path in common.STORAGE.rglob("*")}
    return tables, files


def mutate(client, aid, did, action, *, content=None):
    if action == "delete":
        return client.delete(f"/api/applications/{aid}/documents/{did}")
    return client.post(f"/api/applications/{aid}/documents",
                       data={"slot_key": "resident_abstract"},
                       files={"file": ("FAKE-original.pdf", content or pdf("SYNTHETIC REPLACEMENT"), "application/pdf")})


@pytest.mark.parametrize("state", ["submitted", "reviewing", "decided", "unknown_future_state"])
@pytest.mark.parametrize("action", ["upload", "delete"])
def test_submitted_mutations_are_409_and_preserve_every_table_and_file(client, monkeypatch, state, action):
    aid, did, target = seed(client, monkeypatch)
    with models.get_session() as session:
        app = session.get(models.Application, aid)
        app.status = state
        session.add(app)
        saved_review = session.exec(select(models.Review).where(models.Review.application_id == aid)).one()
        saved_review.officer_memo = "SYNTHETIC REVIEW MEMO"
        session.add(saved_review)
        session.commit()
    before = snapshot()
    calls = []
    def record(name, original):
        @wraps(original)
        def wrapped(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)
        return wrapped
    for name in ["assess_upload", "read_document", "_replace_existing", "_save_row", "_refresh_nhis_identity"]:
        monkeypatch.setattr(documents, name, record(name, getattr(documents, name)))
    from starlette.datastructures import UploadFile
    original_read = UploadFile.read
    async def record_read(file, *args, **kwargs):
        calls.append("UploadFile.read")
        return await original_read(file, *args, **kwargs)
    monkeypatch.setattr(UploadFile, "read", record_read)
    response = mutate(client, aid, did, action)
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "제출한 신청서의 서류는 변경하거나 삭제할 수 없습니다."}
    assert calls == []
    assert snapshot() == before
    assert target.is_file()


def test_draft_reupload_uses_unique_file_and_delete_retains_other_owner(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch, submit=False)
    before_bytes = original.read_bytes()
    first = mutate(client, aid, did, "upload")
    assert first.status_code == 200, first.text
    with models.get_session() as session:
        row = session.exec(select(models.Document).where(models.Document.application_id == aid,
                                                        models.Document.slot_key == "resident_abstract")).one()
        first_path = common.STORAGE.parent / row.file_path
    second = mutate(client, aid, first.json()["document_id"], "upload", content=pdf("SYNTHETIC SECOND"))
    assert second.status_code == 200, second.text
    with models.get_session() as session:
        row = session.exec(select(models.Document).where(models.Document.application_id == aid,
                                                        models.Document.slot_key == "resident_abstract")).one()
        second_path = common.STORAGE.parent / row.file_path
    assert original.read_bytes() == before_bytes
    assert first_path != second_path and first_path.is_file() and second_path.is_file()
    assert mutate(client, aid, row.id, "delete").status_code == 200
    assert not second_path.exists()


def test_submitted_original_read_and_officer_review_remain_available(client, monkeypatch):
    aid, did, original = seed(client, monkeypatch)
    assert client.get(f"/api/files/{did}").content == original.read_bytes()
    assert client.get(f"/api/applications/{aid}/documents").status_code == 200
    authenticate_officer(client, monkeypatch)
    assert client.get(f"/api/officer/applications/{aid}").status_code == 200
    assert client.get(f"/api/files/{did}").content == original.read_bytes()


def test_internal_replacement_rechecks_persisted_state(client, monkeypatch):
    aid, did, target = seed(client, monkeypatch)
    before = snapshot()
    with pytest.raises(Exception) as failure:
        documents._replace_existing(application_id=aid, slot_key="resident_abstract")
    assert getattr(failure.value, "status_code", None) == 409
    assert snapshot() == before


def test_replacement_failure_rolls_back_rows_and_removes_staged_file(client, monkeypatch):
    aid, did, target = seed(client, monkeypatch, submit=False)
    before = snapshot()
    original_save = documents._save_row
    def fail_after_save(*args, **kwargs):
        original_save(*args, **kwargs)
        raise RuntimeError("SYNTHETIC DATABASE FAILURE")
    monkeypatch.setattr(documents, "_save_row", fail_after_save)
    with pytest.raises(RuntimeError, match="SYNTHETIC DATABASE FAILURE"):
        mutate(client, aid, did, "upload")
    assert snapshot() == before
    assert not list(common.STORAGE.rglob("*.deleting-*"))


def test_deletion_failure_restores_file_and_document(client, monkeypatch):
    aid, did, target = seed(client, monkeypatch, submit=False)
    before = snapshot()
    original_commit = models.Session.commit
    def fail_deleted(session):
        if any(isinstance(row, models.Document) for row in session.deleted):
            original_commit(session)
            raise RuntimeError("SYNTHETIC DATABASE FAILURE")
        return original_commit(session)
    monkeypatch.setattr(models.Session, "commit", fail_deleted)
    with pytest.raises(RuntimeError, match="SYNTHETIC DATABASE FAILURE"):
        mutate(client, aid, did, "delete")
    assert snapshot() == before
    assert not list(common.STORAGE.rglob("*.deleting-*"))


@pytest.mark.parametrize("action", ["upload", "delete"])
def test_submit_wins_then_earlier_waiting_mutation_is_rejected(client, monkeypatch, action):
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    original_review = review._run_review
    def paused_review(app):
        entered.set()
        assert release.wait(5), "test did not release submission"
        return original_review(app)
    monkeypatch.setattr(review, "_run_review", paused_review)
    def pending_mutation():
        attempted.set()
        return mutate(client, aid, did, action)
    with ThreadPoolExecutor(2) as pool:
        submission = pool.submit(client.post, f"/api/applications/{aid}/submit")
        try:
            assert entered.wait(5)
            mutation = pool.submit(pending_mutation)
            assert attempted.wait(5)
            assert not mutation.done()
        finally:
            release.set()
        assert submission.result(timeout=10).status_code == 200
        before = snapshot()
        assert mutation.result(timeout=10).status_code == 409
    assert snapshot() == before
    assert target.is_file()


def test_upload_first_finishes_before_submit_and_late_upload_is_rejected(client, monkeypatch):
    import asyncio
    from starlette.datastructures import UploadFile
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release = threading.Event(), threading.Event()
    original_read = UploadFile.read
    async def paused_read(file, *args, **kwargs):
        if file.filename == "FAKE-original.pdf":
            entered.set()
            assert await asyncio.to_thread(release.wait, 5)
        return await original_read(file, *args, **kwargs)
    monkeypatch.setattr(UploadFile, "read", paused_read)
    with ThreadPoolExecutor(2) as pool:
        uploading = pool.submit(mutate, client, aid, did, "upload")
        try:
            assert entered.wait(5)
            submitting = pool.submit(client.post, f"/api/applications/{aid}/submit")
            assert not submitting.done()
        finally:
            release.set()
        assert uploading.result(timeout=10).status_code == 200
        assert submitting.result(timeout=10).status_code == 200
    before = snapshot()
    assert mutate(client, aid, did, "upload").status_code == 409
    assert snapshot() == before


def test_delete_first_completes_before_submit_rechecks_missing_required_document(client, monkeypatch):
    from pathlib import Path
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release = threading.Event(), threading.Event()
    original_rename = Path.rename
    def paused_rename(path, destination):
        if path == target:
            entered.set()
            assert release.wait(5)
        return original_rename(path, destination)
    monkeypatch.setattr(Path, "rename", paused_rename)
    with ThreadPoolExecutor(2) as pool:
        deletion = pool.submit(mutate, client, aid, did, "delete")
        try:
            assert entered.wait(5)
            submitting = pool.submit(client.post, f"/api/applications/{aid}/submit")
            assert not submitting.done()
        finally:
            release.set()
        assert deletion.result(timeout=10).status_code == 200
        assert submitting.result(timeout=10).status_code == 400
    with models.get_session() as session:
        assert session.get(models.Application, aid).status == "draft"
        assert session.exec(select(models.Review).where(models.Review.application_id == aid)).first() is None


def test_two_same_slot_uploads_are_serial_and_keep_both_originals(client, monkeypatch):
    import asyncio
    from starlette.datastructures import UploadFile
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release = threading.Event(), threading.Event()
    original_read = UploadFile.read
    calls = []
    async def paused_read(file, *args, **kwargs):
        calls.append(file.filename)
        if len(calls) == 1:
            entered.set()
            assert await asyncio.to_thread(release.wait, 5)
        return await original_read(file, *args, **kwargs)
    monkeypatch.setattr(UploadFile, "read", paused_read)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(mutate, client, aid, did, "upload")
        try:
            assert entered.wait(5)
            second = pool.submit(mutate, client, aid, did, "upload", content=pdf("SYNTHETIC SECOND"))
            assert len(calls) == 1
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 200
        assert second.result(timeout=10).status_code == 200
    with models.get_session() as session:
        assert len(session.exec(select(models.Document).where(models.Document.application_id == aid,
                                                           models.Document.slot_key == "resident_abstract")).all()) == 1
    files = list((target.parent).rglob("*.pdf"))
    assert len(files) == 3
    assert len({path.read_bytes() for path in files}) == 3


def test_same_host_other_process_submission_waits_for_upload(client, monkeypatch, tmp_path):
    """A second Python process calls the real submit handler on the same fake DB."""
    import asyncio
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import time
    from starlette.datastructures import UploadFile
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release = threading.Event(), threading.Event()
    original_read = UploadFile.read
    async def paused_read(file, *args, **kwargs):
        entered.set()
        assert await asyncio.to_thread(release.wait, 10)
        return await original_read(file, *args, **kwargs)
    monkeypatch.setattr(UploadFile, "read", paused_read)
    started, completed = tmp_path / "worker-started", tmp_path / "worker-completed"
    script = '''
import json,sys
from pathlib import Path
from sqlmodel import create_engine
from demo.backend import models
models.engine=create_engine(sys.argv[1],connect_args={"check_same_thread":False})
from demo.backend.api import common,forms,review
common.STORAGE=Path(sys.argv[2]);forms.STORAGE=common.STORAGE
Path(sys.argv[4]).write_text("started")
result=review.submit(int(sys.argv[3]))
Path(sys.argv[5]).write_text(json.dumps(result))
'''
    worker = None
    with ThreadPoolExecutor(1) as pool:
        uploading = pool.submit(mutate, client, aid, did, "upload")
        try:
            assert entered.wait(5)
            worker = subprocess.Popen([sys.executable, "-B", "-c", script, str(models.engine.url),
                                       str(common.STORAGE), str(aid), str(started), str(completed)],
                                      cwd=Path(__file__).resolve().parents[3], env=os.environ.copy(),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 5
            while not started.exists() and time.monotonic() < deadline:
                assert worker.poll() is None, worker.communicate()
                time.sleep(0.01)
            assert started.exists()
            assert not completed.exists(), "submit escaped the upload's cross-process lock"
        finally:
            release.set()
        assert uploading.result(timeout=15).status_code == 200
    try:
        stdout, stderr = worker.communicate(timeout=15)
        assert worker.returncode == 0, (stdout, stderr)
        assert json.loads(completed.read_text())["status"] == "submitted"
    finally:
        if worker is not None and worker.poll() is None:
            worker.kill()
            worker.communicate()
    before = snapshot()
    assert mutate(client, aid, did, "upload").status_code == 409
    assert snapshot() == before


def test_async_lock_cancellation_releases_for_next_writer(client, monkeypatch):
    import asyncio
    from demo.backend.application_writes import application_write_async
    aid, did, target = seed(client, monkeypatch, submit=False)
    async def exercise():
        entered = asyncio.Event()
        async def holder():
            async with application_write_async(aid):
                entered.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(holder())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with asyncio.timeout(1):
            async with application_write_async(aid):
                pass
    asyncio.run(exercise())
    assert mutate(client, aid, did, "upload").status_code == 200


def test_draft_cannot_delete_other_applications_document(client, monkeypatch):
    aid, did, target = seed(client, monkeypatch, submit=False)
    with models.get_session() as session:
        other = models.Application(application_no="FAKE-OTHER", program_code="double_savings")
        session.add(other)
        session.commit()
        session.refresh(other)
        other_document = models.Document(application_id=other.id, slot_key="resident_abstract",
                                         file_path="storage/FAKE-other.pdf", file_format="pdf")
        session.add(other_document)
        session.commit()
        session.refresh(other_document)
        other_did = other_document.id
        other_aid = other.id
    before = snapshot()
    response = client.delete(f"/api/applications/{aid}/documents/{other_did}")
    assert response.status_code == 404
    assert snapshot() == before
    assert client.delete(f"/api/applications/{other_aid}/documents/{other_did}").status_code == 403
    assert snapshot() == before


def test_status_is_rechecked_after_awaited_upload_read(client, monkeypatch):
    from starlette.datastructures import UploadFile
    aid, did, target = seed(client, monkeypatch, submit=False)
    original_read = UploadFile.read
    after_external_change = []
    async def changed_status(file, *args, **kwargs):
        # Simulate an uncoordinated external writer; official API submission
        # is already excluded by the shared application lock.
        with models.get_session() as session:
            app = session.get(models.Application, aid)
            app.status = "submitted"
            app.submitted_at = datetime(2026, 11, 22)
            session.add(app)
            session.commit()
        after_external_change.append(snapshot())
        return await original_read(file, *args, **kwargs)
    monkeypatch.setattr(UploadFile, "read", changed_status)
    assert mutate(client, aid, did, "upload").status_code == 409
    assert snapshot() == after_external_change[0]


@pytest.mark.parametrize("action", ["signature-scan", "consents"])
def test_signature_and_consent_writes_wait_for_submit_and_cannot_change_snapshot(client, monkeypatch, action):
    aid, did, target = seed(client, monkeypatch, submit=False)
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    original_review = review._run_review
    def paused_review(app):
        entered.set()
        assert release.wait(5)
        return original_review(app)
    monkeypatch.setattr(review, "_run_review", paused_review)
    def pending():
        attempted.set()
        if action == "signature-scan":
            return client.post(f"/api/applications/{aid}/forms/signature-scan",
                               files={"file": ("FAKE-signature.png", b"SYNTHETIC", "image/png")})
        return client.post(f"/api/applications/{aid}/consents", json={"consents": [
            {"consent_type": "admin_info", "agreed": True,
             "signature_data_url": "data:image/png;base64,U1lOVEhFVElD", "signature_kind": "electronic"}]})
    with ThreadPoolExecutor(2) as pool:
        submission = pool.submit(client.post, f"/api/applications/{aid}/submit")
        try:
            assert entered.wait(5)
            mutation = pool.submit(pending)
            assert attempted.wait(5)
            assert not mutation.done()
        finally:
            release.set()
        assert submission.result(timeout=10).status_code == 200
        before = snapshot()
        assert mutation.result(timeout=10).status_code == 409
    assert snapshot() == before


def test_nested_delete_rejected_before_file_change_and_outer_rollback_preserves_original(client, monkeypatch):
    aid, did, target = seed(client, monkeypatch, submit=False)
    before = snapshot()
    with pytest.raises(RuntimeError, match="SYNTHETIC OUTER ROLLBACK"):
        with models.session_transaction():
            with pytest.raises(RuntimeError, match="Nested service transactions are unsupported"):
                documents.delete_document(application_id=aid, document_id=did)
            assert target.is_file()
            raise RuntimeError("SYNTHETIC OUTER ROLLBACK")
    assert snapshot() == before


def test_postcommit_tombstone_cleanup_failure_is_logical_success_and_safe_warning(client, monkeypatch, caplog):
    from pathlib import Path
    aid, did, target = seed(client, monkeypatch, submit=False)
    original = target.read_bytes()
    original_unlink = Path.unlink
    def fail_cleanup(path, *args, **kwargs):
        if ".deleting-" in path.name:
            raise OSError("SYNTHETIC STORAGE CLEANUP FAILURE")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    response = mutate(client, aid, did, "delete")
    assert response.status_code == 200
    with models.get_session() as session:
        assert session.get(models.Document, did) is None
    assert not target.exists()
    tombstones = list(target.parent.glob("*.deleting-*"))
    assert len(tombstones) == 1 and tombstones[0].read_bytes() == original
    messages = [record.getMessage() for record in caplog.records if record.name == documents.__name__]
    assert messages == ["문서 삭제 후 임시 파일 정리를 완료하지 못했습니다."]
