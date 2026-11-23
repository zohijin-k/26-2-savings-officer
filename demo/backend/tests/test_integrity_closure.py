"""Synthetic counterexamples; no OCR, real data or network."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event, delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine, select
from demo.backend import models
from demo.backend.api.review import _link_overlapping_households
from demo.backend.api.officer import _incoming_household_warnings
from demo.backend.review_revision import update_review


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    path = tmp_path / 'FAKE-integrity.db'
    engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(models, 'engine', engine)
    models.init_db()
    yield path
    engine.dispose()


def add(aid, *, status='draft', year=2026, program='double_savings', member='가상공통', reviewed=False):
    with models.get_session() as s:
        a = models.Application(id=aid, application_no=f'FAKE-INTEGRITY-{aid}', program_code=program,
                              status=status, created_at=datetime(year, 6, 1))
        s.add(a)
        s.add(models.Document(application_id=aid, slot_key='nhis_qualification',
                             doc_type='건강보험자격확인서', file_path=f'FAKE-{aid}.pdf',file_format='pdf',
                             ocr_json={'fields':{'가구원목록':json.dumps([{'성명':member,'생년월일':'2001-01-01'}])}}))
        if reviewed:
            s.add(models.Review(application_id=aid, final_status='PASS', stage2_status='PASS',
                                officer_memo='FAKE memo', officer_decision='approve', officer_role='province',
                                decided_at=datetime(2026, 6, 1), review_payload_json={'reasons':[]}))
        s.commit();s.refresh(a)
        return a


def snapshot(path):
    with closing(sqlite3.connect(path)) as c:
        return {t:c.execute(f'SELECT * FROM {t} ORDER BY id').fetchall()
                for t in ['application','review','document']}


@pytest.mark.parametrize('status,year,program,member,reviewed,overlap', [
    ('decided',2026,'double_savings','가상별개',True,False),
    ('submitted',2026,'double_savings','가상공통',True,True),
    ('decided',2026,'double_savings','가상공통',True,True),
    ('reviewing',2026,'double_savings','가상공통',True,True),
    ('submitted',2025,'double_savings','가상공통',True,False),
    ('submitted',2026,'job_package','가상공통',True,False),
    ('draft',2026,'double_savings','가상공통',True,False),
    ('submitted',2026,'double_savings','가상공통',False,True),
])
def test_overlap_scope_entire_previous_state_and_retry(isolated,status,year,program,member,reviewed,overlap):
    previous=add(1,status=status,year=year,program=program,member=member,reviewed=reviewed)
    current=add(2)
    before=snapshot(isolated)
    r=models.Review(application_id=2,final_status='PASS',stage2_status='PASS')
    _link_overlapping_households(current,r);_link_overlapping_households(current,r)
    assert snapshot(isolated)==before
    assert r.final_status==('NEEDS_REVIEW' if overlap else 'PASS')
    assert len(r.review_payload_json.get('related_applications',[]))==int(overlap)
    if overlap:
        with models.session_transaction():
            with models.get_session() as s:
                a=s.get(models.Application,2);a.status='submitted';s.add(a);s.add(r);s.commit();s.refresh(r)
        assert len(_incoming_household_warnings(previous))==1
        after=snapshot(isolated)
        assert after["application"][0] == before["application"][0]
        assert after["document"] == before["document"]
        assert after["review"][:len(before["review"])] == before["review"]


def test_multiple_edges_rollback_retry_and_no_partial_warning(isolated):
    first=add(1,status='decided',reviewed=True);add(2,status='reviewing',reviewed=True)
    current=add(3);before=snapshot(isolated)
    with pytest.raises(RuntimeError,match='FAKE failure'):
        with models.session_transaction():
            r=models.Review(application_id=3,final_status='FAIL',stage2_status='FAIL')
            _link_overlapping_households(current,r)
            assert len(r.review_payload_json['related_applications'])==2
            assert r.final_status=='FAIL'
            with models.get_session() as s:
                a=s.get(models.Application,3);a.status='submitted';s.add(a);s.add(r);s.commit();s.refresh(r)
            raise RuntimeError('FAKE failure')
    assert snapshot(isolated)==before
    assert _incoming_household_warnings(first)==[]
    with models.session_transaction():
        r=models.Review(application_id=3,final_status='PASS',stage2_status='PASS')
        _link_overlapping_households(current,r)
        with models.get_session() as s:
            a=s.get(models.Application,3);a.status='submitted';s.add(a);s.add(r);s.commit();s.refresh(r)
    assert r.final_status=='NEEDS_REVIEW'
    assert len(_incoming_household_warnings(first))==1


def test_concurrent_submission_one_persistent_edge_no_duplicate_or_old_mutation(isolated):
    add(1);add(2)
    def submit(aid):
        with models.session_transaction():
            with models.get_session() as s:
                a=s.get(models.Application,aid)
                r=models.Review(application_id=aid,final_status='PASS',stage2_status='PASS')
                _link_overlapping_households(a,r)
                a.status='submitted';s.add(a);s.add(r);s.commit();s.refresh(r)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(submit,[1,2]))
    with models.get_session() as s:
        reviews=s.exec(select(models.Review)).all()
        assert sorted(r.final_status for r in reviews)==['NEEDS_REVIEW','PASS']
        assert [r.revision for r in reviews]==[1,1]
        assert sum(len(r.review_payload_json.get('related_applications',[])) for r in reviews)==1


ATTACKS=[
 'DELETE FROM review WHERE application_id=1',
 'DELETE FROM review',
 "INSERT OR REPLACE INTO application (id,application_no,program_code,status,created_at,updated_at) VALUES(99,'FAKE-INTEGRITY-1','double_savings','draft',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
 "UPDATE OR REPLACE application SET application_no='FAKE-INTEGRITY-2' WHERE id=1",
 'DELETE FROM application WHERE id=1',
 'UPDATE application SET id=99 WHERE id=1',
 'UPDATE OR REPLACE application SET id=2 WHERE id=1',
 "INSERT OR REPLACE INTO application (id,application_no,program_code,status,created_at,updated_at) VALUES(1,'FAKE-ABA','double_savings','draft',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
 'UPDATE review SET id=99, revision=revision+1 WHERE application_id=1',
 'UPDATE review SET application_id=3, revision=revision+1 WHERE application_id=1',
 'UPDATE OR REPLACE review SET application_id=2, revision=revision+1 WHERE application_id=1',
 'UPDATE OR REPLACE review SET id=2, revision=revision+1 WHERE application_id=1',
 "INSERT OR REPLACE INTO review (id, application_id, final_status, revision, created_at) VALUES (1,2,'PASS',1,CURRENT_TIMESTAMP)",
 "INSERT INTO review (application_id,final_status,revision,created_at) VALUES(1,'PASS',1,CURRENT_TIMESTAMP) ON CONFLICT(application_id) DO UPDATE SET revision=review.revision+1",
 'UPDATE review SET revision=1 WHERE application_id=1',
]
@pytest.mark.parametrize('recursive',[0,1])
@pytest.mark.parametrize('foreign',[0,1])
@pytest.mark.parametrize('sql',ATTACKS)
def test_sqlite_attack_matrix_is_connection_setting_independent(isolated,recursive,foreign,sql):
    add(1,status='decided',reviewed=True);add(2,status='reviewing',reviewed=True)
    before=snapshot(isolated)
    with closing(sqlite3.connect(isolated)) as c:
        c.execute(f'PRAGMA recursive_triggers={recursive}');c.execute(f'PRAGMA foreign_keys={foreign}')
        assert c.execute('PRAGMA recursive_triggers').fetchone()==(recursive,)
        assert c.execute('PRAGMA foreign_keys').fetchone()==(foreign,)
        with pytest.raises(sqlite3.IntegrityError,match='REVIEW_WRITE_GUARD'):
            c.execute(sql)
        c.rollback()
    assert snapshot(isolated)==before
    with models.session_transaction():
        with models.get_session() as s:
            assert update_review(s,1,1,officer_memo='FAKE after rejection')==2;s.commit()


@pytest.mark.parametrize('method',['orm','bulk','merge'])
def test_orm_delete_bulk_and_merge_identity_cannot_bypass(isolated,method):
    add(1,status='decided',reviewed=True);before=snapshot(isolated)
    with models.get_session() as s:
        r=s.exec(select(models.Review)).one()
        with pytest.raises(IntegrityError,match='REVIEW_WRITE_GUARD'):
            if method=='orm':s.delete(r)
            elif method=='bulk':s.execute(delete(models.Review))
            else:
                r.application_id=99;s.merge(r)
            s.commit()
        s.rollback()
    assert snapshot(isolated)==before


def test_migration_interruption_rolls_back_all_ddl_and_preserves_legacy_rows(tmp_path,monkeypatch):
    path=tmp_path/'FAKE-legacy.db';engine=create_engine(f'sqlite:///{path}')
    monkeypatch.setattr(models,'engine',engine)
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT, officer_memo TEXT, officer_decision TEXT)')
        c.exec_driver_sql("INSERT INTO review VALUES(7,42,'FAIL','FAKE legacy memo','reject')")
    with closing(sqlite3.connect(path)) as c:before='\n'.join(c.iterdump())
    def interrupt(conn,cursor,statement,params,context,executemany):
        if statement==models.REVIEW_IDENTITY_GUARD_DDL:raise KeyboardInterrupt('FAKE migration interruption')
    event.listen(engine,'before_cursor_execute',interrupt)
    with pytest.raises(KeyboardInterrupt):models._add_missing_columns()
    event.remove(engine,'before_cursor_execute',interrupt)
    with closing(sqlite3.connect(path)) as c:assert '\n'.join(c.iterdump())==before
    models._add_missing_columns();models._add_missing_columns()
    with closing(sqlite3.connect(path)) as c:
        assert c.execute('SELECT id,application_id,officer_memo,officer_decision,revision FROM review').fetchone()==(7,42,'FAKE legacy memo','reject',1)
        assert dict(c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))==dict(models.REVIEW_WRITE_GUARDS)
    engine.dispose()
