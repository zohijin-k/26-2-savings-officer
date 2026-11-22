"""Synthetic real SQLite CAS, migration, independent connections and processes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import multiprocessing
import sqlite3
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, create_engine, select

PROGRAM='double_savings'

from demo.backend import models
from demo.backend.api import officer
from demo.backend.main import app
from demo.backend.tests.test_portal_uploads import client


@pytest.fixture(autouse=True)
def officer_session(client,monkeypatch):
    from demo.backend.tests.security_support import authenticate_officer
    authenticate_officer(client,monkeypatch)


def state(aid):
    with models.get_session() as session:
        review = session.exec(select(models.Review).where(models.Review.application_id == aid)).one()
        application = session.get(models.Application, aid)
        return review.model_dump(), application.model_dump()


@pytest.fixture
def record(client):
    with models.get_session() as session:
        application = models.Application(application_no="FAKE-CAS-1", program_code=PROGRAM, status="submitted")
        session.add(application); session.flush()
        aid = application.id
        session.add(models.Review(application_id=aid, final_status="NEEDS_REVIEW", officer_memo="synthetic baseline"))
        session.commit()
    return aid


def save(client, aid, expected=1, decision="hold", memo="synthetic updated", **extra):
    return client.post(f"/api/officer/applications/{aid}/decision", json={
        "role":"province", "decision":decision, "memo":memo, "expected_revision":expected, **extra})


def test_matching_revision_and_every_valid_write_increments_once(client, record):
    for revision in range(1, 4):
        result = save(client, record, revision)
        assert result.status_code == 200, result.text
        assert result.json()["revision"] == revision + 1
        review, application = state(record)
        assert review["revision"] == revision + 1 and review["officer_memo"] == "synthetic updated"
        assert review["officer_decision"] == "hold" and application["status"] == "reviewing"
        assert client.get(f"/api/officer/applications/{record}").json()["revision"] == revision + 1


@pytest.mark.parametrize("decision", ["hold", "approve", "reject"])
def test_stale_revision_preserves_entire_review_and_application(client, record, decision):
    assert save(client, record).status_code == 200
    before = state(record)
    result = save(client, record, 1, decision, "stale synthetic memo")
    assert result.status_code == 409 and result.json()["detail"]["code"] == "REVIEW_REVISION_CONFLICT"
    assert state(record) == before
    assert "synthetic" not in result.text


def test_missing_revision_rejected_for_direct_http_and_service(client, record):
    before = state(record)
    response = client.post(f"/api/officer/applications/{record}/decision", json={"decision":"hold", "memo":"legacy"})
    assert response.status_code == 428 and response.json()["detail"]["code"] == "REVIEW_REVISION_REQUIRED"
    with pytest.raises(HTTPException) as caught:
        officer._apply_decision(record, officer.get_role("province"), "hold", "legacy")
    assert caught.value.status_code == 428
    assert state(record) == before


@pytest.mark.parametrize("expected", [None, 0, -1, True, "1", 1.5, 999999, 2**100])
def test_invalid_or_forged_revision_never_changes_db(client, record, expected):
    before = state(record); result = save(client, record, expected)
    assert result.status_code == (428 if expected is None else 409 if expected == 999999 else 422)
    assert state(record) == before


def test_client_cannot_set_new_revision(client, record):
    result = save(client, record, revision=999)
    assert result.status_code == 422
    assert state(record)[0]["revision"] == 1


def test_unauthenticated_and_wrong_application_cannot_modify_record(client, record):
    before = state(record)
    with closing(TestClient(app)) as anonymous:
        assert save(anonymous, record).status_code == 401
    assert save(client, record, role="invalid-role").status_code == 400
    assert save(client, record + 10000).status_code == 404
    assert client.post(f"/api/applications/{record}/decision", json={"expected_revision":1}).status_code == 403
    assert state(record) == before


def test_no_review_decision_does_not_create_one(client):
    with models.get_session() as session:
        application = models.Application(application_no="FAKE-NO-REVIEW", program_code=PROGRAM, status="submitted")
        session.add(application); session.commit(); aid=application.id
    assert save(client, aid).status_code == 400
    with models.get_session() as session:
        assert session.exec(select(models.Review).where(models.Review.application_id == aid)).first() is None


def test_commit_failure_rolls_back_cas_and_application(client, record):
    before=state(record)
    def fail(connection): raise RuntimeError("synthetic transaction failure")
    event.listen(models.engine, "commit", fail)
    try:
        with closing(TestClient(app, raise_server_exceptions=False)) as requester:
            requester.cookies.update(client.cookies)
            assert save(requester,record).status_code == 500
    finally: event.remove(models.engine, "commit", fail)
    assert state(record)==before
    assert save(client, record).status_code == 200


def test_bulk_conflict_is_all_or_nothing_and_tokens_required(client, record):
    with models.get_session() as session:
        application=models.Application(application_no="FAKE-CAS-2",program_code=PROGRAM,status="submitted")
        session.add(application);session.flush(); other=application.id
        session.add(models.Review(application_id=other,final_status="NEEDS_REVIEW"));session.commit()
    assert save(client, other).status_code==200
    before=state(record),state(other)
    body={"decision":"hold","memo":"bulk synthetic","application_ids":[record,other],"expected_revisions":{str(record):1,str(other):1}}
    result=client.post("/api/officer/applications/decisions",json=body)
    assert result.status_code==409 and result.json()["detail"]["code"]=="REVIEW_REVISION_CONFLICT"
    assert (state(record),state(other))==before
    body.pop("expected_revisions")
    assert client.post("/api/officer/applications/decisions",json=body).status_code==428
    assert (state(record),state(other))==before
    body["expected_revisions"]={str(record):1,str(other):2}
    assert client.post("/api/officer/applications/decisions",json=body).status_code==200
    assert state(record)[0]["revision"]==2 and state(other)[0]["revision"]==3


def test_independent_connections_same_revision_have_one_winner(client, record):
    from threading import Barrier
    barrier=Barrier(2); connections=set()
    def run(memo):
        # Hold two independently checked-out DB connections, then release reads.
        with models.engine.connect() as connection:
            connections.add(id(connection.connection.dbapi_connection))
            assert connection.exec_driver_sql("SELECT revision FROM review WHERE application_id=?",(record,)).scalar()==1
            barrier.wait(timeout=10)
        try: return officer._apply_decision(record,officer.get_role("province"),"hold",memo,expected_revision=1)
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,["connection A","connection B"]))
    assert len(connections)==2 and sum(isinstance(x,dict) for x in results)==1 and results.count(409)==1
    saved=state(record)[0]; assert saved["revision"]==2 and saved["officer_memo"] in ("connection A","connection B")


def process_worker(url, aid, barrier, queue, memo, action="save"):
    models.engine=create_engine(url,connect_args={"check_same_thread":False})
    try:
        if action=="create":
            barrier.wait(timeout=15)
            with models.session_transaction():
                with models.get_session() as session:
                    session.add(models.Review(application_id=aid,final_status="NEEDS_REVIEW",officer_memo=memo));session.commit()
            queue.put(200)
        else:
            with models.get_session() as session:
                revision=session.exec(select(models.Review).where(models.Review.application_id==aid)).one().revision
            barrier.wait(timeout=15)
            result=officer._apply_decision(aid,officer.get_role("province"),"hold" if memo=="A" else "reject",memo,expected_revision=revision)
            queue.put((200,result["revision"]))
    except HTTPException as error: queue.put((error.status_code,error.detail))
    except IntegrityError: queue.put(409)
    finally: models.engine.dispose()


def test_separate_spawned_processes_same_revision_one_winner(client, record):
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(2);queue=context.Queue()
    workers=[context.Process(target=process_worker,args=(str(models.engine.url),record,barrier,queue,memo))for memo in ["A","B"]]
    for worker in workers:worker.start()
    try:
        results=[queue.get(timeout=25)for _ in workers]
        assert sorted(x[0]for x in results)==[200,409]
        saved,application=state(record)
        assert saved["revision"]==2 and saved["officer_memo"] in ("A","B")
        assert application["status"]==("reviewing" if saved["officer_decision"]=="hold" else "decided")
    finally:
        for worker in workers:
            worker.join(5)
            if worker.is_alive():worker.terminate();worker.join(5)
        assert all(worker.exitcode==0 for worker in workers)


def test_first_creation_race_is_unique_across_processes(client):
    with models.get_session() as session:
        application=models.Application(application_no="FAKE-CREATE",program_code=PROGRAM,status="submitted")
        session.add(application);session.commit();aid=application.id
    context=multiprocessing.get_context("spawn");barrier=context.Barrier(2);queue=context.Queue()
    workers=[context.Process(target=process_worker,args=(str(models.engine.url),aid,barrier,queue,memo,"create"))for memo in ["A","B"]]
    for worker in workers:worker.start()
    try:assert sorted(queue.get(timeout=25)for _ in workers)==[200,409]
    finally:
        for worker in workers:
            worker.join(5)
            if worker.is_alive():worker.terminate();worker.join(5)
        assert all(worker.exitcode==0 for worker in workers)
    with models.get_session() as session:
        rows=session.exec(select(models.Review).where(models.Review.application_id==aid)).all()
        assert len(rows)==1 and rows[0].revision==1


def crash_worker(url,aid,ready):
    models.engine=create_engine(url,connect_args={"check_same_thread":False})
    with models.session_transaction():
        officer._apply_decision(aid,officer.get_role("province"),"hold","never committed",expected_revision=1)
        ready.set()
        # Parent terminates this process after the real CAS and savepoint release.
        import time
        time.sleep(25)


def test_process_termination_before_outer_commit_has_no_partial_write(client,record):
    before=state(record);context=multiprocessing.get_context("spawn");ready=context.Event()
    worker=context.Process(target=crash_worker,args=(str(models.engine.url),record,ready));worker.start()
    try:assert ready.wait(15)
    finally:worker.terminate();worker.join(10)
    assert worker.exitcode != 0 and state(record)==before
    assert save(client,record).status_code==200


def test_response_loss_recovery_reads_without_duplicate_write(client,record):
    before=client.get(f"/api/officer/applications/{record}").json()["revision"]
    save(client,record,before) # Simulate losing only the HTTP acknowledgment.
    observed=client.get(f"/api/officer/applications/{record}").json()
    assert observed["revision"]==before+1 and observed["decision"]["memo"]=="synthetic updated"
    snapshot=state(record)
    assert save(client,record,before).status_code==409 and state(record)==snapshot


def test_orm_system_writer_bumps_revision_and_stale_orm_cannot_bypass(client,record):
    with Session(models.engine) as first, Session(models.engine) as second:
        left=first.exec(select(models.Review).where(models.Review.application_id==record)).one()
        right=second.exec(select(models.Review).where(models.Review.application_id==record)).one()
        left.final_status="FAIL";first.add(left);first.commit()
        before=state(record);assert before[0]["revision"]==2
        right.officer_memo="stale ORM";second.add(right)
        with pytest.raises(StaleDataError):second.commit()
        second.rollback();assert state(record)==before
    assert save(client,record,1).status_code==409 and state(record)==before


def test_legacy_migration_preserves_values_defaults_unique_and_reapplication(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'legacy.db'}")
    monkeypatch.setattr(models,"engine",engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT, officer_decision TEXT, officer_memo TEXT)")
        connection.exec_driver_sql("INSERT INTO review VALUES (1,10,'FAIL','hold','synthetic legacy memo')")
    for _ in range(2):models._add_missing_columns()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT final_status,officer_decision,officer_memo,revision FROM review").one()==("FAIL","hold","synthetic legacy memo",1)
        column=next(x for x in connection.exec_driver_sql("PRAGMA table_info(review)")if x[1]=="revision")
        assert column[3]==1 and str(column[4])=="1"
    with models.session_transaction():
        with models.get_session() as session:
            from demo.backend.review_revision import update_review
            assert update_review(session,10,1,officer_memo="migrated CAS")==2
            session.commit()
    with engine.connect() as connection:assert connection.exec_driver_sql("SELECT revision,officer_memo FROM review").one()==(2,"migrated CAS")
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:connection.exec_driver_sql("INSERT INTO review (application_id,final_status) VALUES(10,'PASS')")
    engine.dispose()


def test_duplicate_legacy_reviews_stop_migration_without_deletion(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'duplicates.db'}");monkeypatch.setattr(models,"engine",engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT)")
        connection.exec_driver_sql("INSERT INTO review VALUES(1,10,'FAIL'),(2,10,'PASS')")
    with pytest.raises(RuntimeError,match="duplicate application reviews"):models._add_missing_columns()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT * FROM review").all()==[(1,10,"FAIL"),(2,10,"PASS")]
        assert "revision" not in [x[1]for x in connection.exec_driver_sql("PRAGMA table_info(review)")]
    engine.dispose()


def test_submission_never_deletes_an_existing_review_or_resets_its_revision(client,record,monkeypatch):
    from demo.backend.api import review
    from demo.backend.tests.security_support import claim_synthetic_application
    with models.get_session() as session:
        application=session.get(models.Application,record);application.status="draft";session.add(application);session.commit()
    claim_synthetic_application(client,record)
    monkeypatch.setattr(review,"_blockers",lambda application:[])
    monkeypatch.setattr(review,"_run_review",lambda application:models.Review(application_id=record,final_status="PASS"))
    from demo.backend.api import forms
    monkeypatch.setattr(forms,"snapshot_written_pdf",lambda application:(None,0))
    before=state(record)
    assert client.post(f"/api/applications/{record}/submit").status_code==409
    assert state(record)==before


def test_migration_ddl_failure_rolls_back_all_added_columns(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'failed-migration.db'}");monkeypatch.setattr(models,"engine",engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT, officer_memo TEXT)")
        connection.exec_driver_sql("INSERT INTO review VALUES(1,10,'FAIL','synthetic preserved')")
    def fail(connection,cursor,statement,parameters,context,many):
        if statement.startswith("CREATE UNIQUE INDEX IF NOT EXISTS uq_review_application"):
            raise RuntimeError("synthetic migration interruption")
    event.listen(engine,"before_cursor_execute",fail)
    try:
        with pytest.raises(RuntimeError,match="synthetic migration interruption"):models._add_missing_columns()
    finally:event.remove(engine,"before_cursor_execute",fail)
    with engine.connect() as connection:
        assert [row[1]for row in connection.exec_driver_sql("PRAGMA table_info(review)")]==['id','application_id','final_status','officer_memo']
        assert connection.exec_driver_sql("SELECT * FROM review").one()==(1,10,'FAIL','synthetic preserved')
    models._add_missing_columns()
    with engine.connect() as connection:assert connection.exec_driver_sql("SELECT revision FROM review").scalar_one()==1
    engine.dispose()


def test_invalid_legacy_revision_stops_without_silent_reset(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'invalid-revision.db'}");monkeypatch.setattr(models,"engine",engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT, officer_memo TEXT, revision INTEGER)")
        connection.exec_driver_sql("INSERT INTO review VALUES(1,10,'FAIL','synthetic preserved',NULL)")
    with pytest.raises(RuntimeError,match="invalid revision"):models._add_missing_columns()
    with engine.connect() as connection:assert connection.exec_driver_sql("SELECT * FROM review").one()==(1,10,'FAIL','synthetic preserved',None)
    engine.dispose()


def test_memo_then_final_decision_and_stale_post_final_memo(client,record):
    assert save(client,record,1,"hold","synthetic working memo").status_code==200
    final=save(client,record,2,"reject","synthetic final memo")
    assert final.status_code==200 and final.json()["revision"]==3
    before=state(record)
    assert before[0]["officer_decision"]=="reject" and before[1]["status"]=="decided"
    result=save(client,record,2,"hold","synthetic stale after final")
    assert result.status_code==409 and result.json()["detail"]["code"]=="REVIEW_REVISION_CONFLICT"
    assert state(record)==before
