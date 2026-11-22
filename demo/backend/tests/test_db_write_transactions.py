"""Synthetic spawned processes; independent flock directories, shared SQLite file.

These tests exercise the real mutation handlers and transaction/file boundaries.
OCR and submission eligibility are explicit concurrency stubs, always REVIEW;
policy/OCR/ownership behavior is covered by the existing HTTP regression suites.
"""
import asyncio
from hashlib import sha256
from io import BytesIO
import multiprocessing
import os
from pathlib import Path
import tempfile
import traceback

import pytest
from sqlmodel import Session, create_engine, select

from demo.backend import models
from demo.backend.api import common, documents, forms
from demo.backend.tests.test_portal_uploads import client


def _worker(url, storage, namespace, aid, action, output, entered=None, release=None,
            document_id=None, content=b"synthetic document"):
    from fastapi import HTTPException
    from starlette.datastructures import UploadFile
    from demo.backend.api import applications, review
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_check import CheckResult
    from demo.backend.rules.doc_types import DocType

    models.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": .15})
    models.SQLITE_BUSY_TIMEOUT_MS = 150
    tempfile.tempdir = namespace
    for module in (common, documents, forms, applications):
        module.STORAGE = Path(storage)
    documents.DOCUMENTS = Path(storage) / "documents"
    review._blockers = lambda app: []
    def run_review(app):
        if action == "paused_submit":
            entered.set()
            assert release.wait(15)
        return models.Review(application_id=aid, final_status="NEEDS_REVIEW")
    review._run_review = run_review
    forms.snapshot_written_pdf = lambda app: (None, 0)
    def assess(*args, **kwargs):
        if action == "paused_ocr":
            entered.set()
            assert release.wait(15)
        return (OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT),
                CheckResult(status="NEEDS_REVIEW", findings=[]))
    documents.assess_upload = assess
    original_get = Session.get
    paused = False
    def get(session, entity, ident, *args, **kwargs):
        nonlocal paused
        result = original_get(session, entity, ident, *args, **kwargs)
        if action == "paused_upload" and entity is models.Application and not paused:
            import inspect
            if any(frame.function == "_save_row" for frame in inspect.stack()):
                paused = True
                entered.set()
                assert release.wait(15)
        return result
    Session.get = get
    if action == "rollback_upload":
        def fail_commit(session):
            raise RuntimeError("synthetic upload commit failure")
        Session.commit = fail_commit
    try:
        if action in {"submit", "paused_submit"}:
            result = review.submit(aid)
        elif action == "delete":
            result = documents.delete_document(aid, document_id)
        else:
            result = asyncio.run(documents.upload_document(
                aid, UploadFile(BytesIO(content), filename="synthetic.pdf"),
                slot_key="resident_abstract", declared_issue_date=None))
        output.put((200, result))
    except HTTPException as exc:
        output.put((exc.status_code, exc.detail))
    except BaseException:
        output.put((500, traceback.format_exc()))
    finally:
        models.engine.dispose()


class Workers:
    def __init__(self, root, aid, url):
        self.root, self.aid, self.url = root, aid, url
        self.context = multiprocessing.get_context("spawn")
        self.processes = []
        self.releases = []

    def barrier(self):
        entered, release = self.context.Event(), self.context.Event()
        self.releases.append(release)
        return entered, release

    def start(self, action, *, url=None, entered=None, release=None, document_id=None,
              content=b"synthetic document"):
        namespace = self.root / f"namespace-{len(self.processes)}"
        namespace.mkdir()
        output = self.context.Queue()
        process = self.context.Process(target=_worker, args=(
            url or self.url, str(common.STORAGE), str(namespace), self.aid, action,
            output, entered, release, document_id, content))
        self.processes.append(process)
        process.start()
        return process, output

    @staticmethod
    def result(worker, expected):
        process, output = worker
        status, detail = output.get(timeout=20)
        process.join(10)
        assert process.exitcode == 0
        assert status == expected, (status, detail)
        return detail

    def close(self):
        for release in self.releases:
            release.set()
        for process in self.processes:
            process.join(15)
            if process.is_alive():
                process.terminate()
                process.join()


@pytest.fixture
def workers(client, tmp_path):
    response = client.post("/api/applications", json={"program_code": "double_savings"})
    assert response.status_code == 200, response.text
    pool = Workers(tmp_path, response.json()["id"], str(models.engine.url))
    try:
        yield pool
    finally:
        pool.close()


def _documents(aid):
    with models.get_session() as session:
        return session.exec(select(models.Document).where(
            models.Document.application_id == aid)).all()


def _database_snapshot():
    with models.get_session() as session:
        return {table.name: sorted([dict(row) for row in session.execute(table.select()).mappings()], key=repr)
                for table in models.SQLModel.metadata.sorted_tables}


def _file_snapshot():
    return {str(path.relative_to(common.STORAGE)): sha256(path.read_bytes()).hexdigest()
            for path in common.STORAGE.rglob("*") if path.is_file()}


def _assert_review_state(aid, status, expected_reviews):
    with models.get_session() as session:
        assert session.get(models.Application, aid).status == status
        reviews = session.exec(select(models.Review).where(models.Review.application_id == aid)).all()
        assert len(reviews) == expected_reviews
        assert all(row.final_status == "NEEDS_REVIEW" for row in reviews)


@pytest.mark.parametrize("path_mode", ["same", "symlink", "relative"])
def test_final_draft_read_is_locked_until_insert_and_commit(workers, path_mode):
    entered, release = workers.barrier()
    url = workers.url
    if path_mode == "symlink":
        alias = workers.root / "alias.db"
        alias.symlink_to(Path(models.engine.url.database))
        url = f"sqlite:///{alias}"
    elif path_mode == "relative":
        relative = os.path.relpath(models.engine.url.database, Path.cwd())
        url = f"sqlite:///{relative}"
    upload = workers.start("paused_upload", entered=entered, release=release)
    assert entered.wait(15), "upload never reached final draft read"
    workers.result(workers.start("submit", url=url), 503)
    release.set()
    workers.result(upload, 200)
    _assert_review_state(workers.aid, "draft", 0)
    assert len(_documents(workers.aid)) == 1
    workers.result(workers.start("submit", url=url), 200)
    _assert_review_state(workers.aid, "submitted", 1)


def test_same_slot_upload_timeout_then_retry_keeps_every_original(workers):
    workers.result(workers.start("upload", content=b"synthetic original"), 200)
    original = common.STORAGE.parent / _documents(workers.aid)[0].file_path
    entered, release = workers.barrier()
    first = workers.start("paused_upload", entered=entered, release=release,
                          content=b"synthetic replacement one")
    assert entered.wait(15)
    workers.result(workers.start("upload", content=b"synthetic replacement two"), 503)
    assert original.read_bytes() == b"synthetic original"
    release.set()
    workers.result(first, 200)
    first_path = common.STORAGE.parent / _documents(workers.aid)[0].file_path
    workers.result(workers.start("upload", content=b"synthetic replacement two"), 200)
    rows = _documents(workers.aid)
    assert len(rows) == 1 and rows[0].slot_key == "resident_abstract"
    latest = common.STORAGE.parent / rows[0].file_path
    assert original.read_bytes() == b"synthetic original"
    assert first_path.read_bytes() == b"synthetic replacement one"
    assert latest.read_bytes() == b"synthetic replacement two"
    assert len({original, first_path, latest}) == 3
    assert len(_file_snapshot()) == 3
    _assert_review_state(workers.aid, "draft", 0)


def test_submit_reservation_blocks_delete_then_submitted_delete_is_conflict(workers):
    workers.result(workers.start("upload"), 200)
    document = _documents(workers.aid)[0]
    before_files = _file_snapshot()
    entered, release = workers.barrier()
    submission = workers.start("paused_submit", entered=entered, release=release)
    assert entered.wait(15)
    before_database = _database_snapshot()
    workers.result(workers.start("delete", document_id=document.id), 503)
    assert _database_snapshot() == before_database and _file_snapshot() == before_files
    release.set()
    workers.result(submission, 200)
    committed_database = _database_snapshot()
    workers.result(workers.start("delete", document_id=document.id), 409)
    assert _database_snapshot() == committed_database and _file_snapshot() == before_files
    _assert_review_state(workers.aid, "submitted", 1)


def test_submission_can_finish_during_ocr_and_late_replacement_is_rejected(workers):
    workers.result(workers.start("upload", content=b"submitted original"), 200)
    before_files = _file_snapshot()
    entered, release = workers.barrier()
    upload = workers.start("paused_ocr", entered=entered, release=release,
                           content=b"late replacement")
    assert entered.wait(15)
    # OCR preparation holds no SQLite writer reservation, so submission succeeds.
    workers.result(workers.start("submit"), 200)
    committed_database = _database_snapshot()
    release.set()
    workers.result(upload, 409)
    assert _database_snapshot() == committed_database and _file_snapshot() == before_files
    # An entirely new post-submit upload also cannot replace the submitted bytes.
    workers.result(workers.start("upload", content=b"post submit replacement"), 409)
    assert _database_snapshot() == committed_database and _file_snapshot() == before_files
    _assert_review_state(workers.aid, "submitted", 1)


def test_upload_rollback_preserves_state_and_allows_another_process_retry(workers):
    workers.result(workers.start("upload", content=b"synthetic original"), 200)
    before_database, before_files = _database_snapshot(), _file_snapshot()
    detail = workers.result(workers.start("rollback_upload", content=b"failed replacement"), 500)
    assert "synthetic upload commit failure" in detail
    assert _database_snapshot() == before_database and _file_snapshot() == before_files
    workers.result(workers.start("upload", content=b"successful retry"), 200)
    assert len(_documents(workers.aid)) == 1
    assert len(_file_snapshot()) == 2
    _assert_review_state(workers.aid, "draft", 0)
