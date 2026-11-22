"""Exact-source independent API contract validation with complete DB snapshots."""
import pytest
from sqlmodel import select
from demo.backend import models
from demo.backend.tests.test_review_revision import client,record
from demo.backend.tests.security_support import authenticate_officer
from demo.backend.review_revision import MAX_EXPECTED_REVISION

@pytest.fixture(autouse=True)
def auth(client,monkeypatch):authenticate_officer(client,monkeypatch)

def snapshot():
    with models.get_session() as s:
        return ([x.model_dump() for x in s.exec(select(models.Review).order_by(models.Review.id))],
                [x.model_dump() for x in s.exec(select(models.Application).order_by(models.Application.id))])

@pytest.fixture
def pair(client,record):
    with models.get_session() as s:
        a=models.Application(application_no='FAKE-CONTRACT-OTHER',program_code='job_package' if hasattr(models.Review,'reject_notice') else 'double_savings',status='submitted')
        s.add(a);s.flush();aid=a.id;s.add(models.Review(application_id=aid,final_status='NEEDS_REVIEW',officer_memo='FAKE baseline other'));s.commit()
    return record,aid

@pytest.mark.parametrize('token',[0,-1,MAX_EXPECTED_REVISION+1,2**100,1.5,1.0,'1','0',True,False,None,[],[1],{}])
@pytest.mark.parametrize('invalid_position',[0,1])
def test_each_bulk_value_is_strict_and_db_remains_unchanged(client,pair,token,invalid_position):
    ids=list(pair);values={str(i):1 for i in ids};values[str(ids[invalid_position])]=token;before=snapshot()
    r=client.post('/api/officer/applications/decisions',json={'role':'province','decision':'hold','memo':'FAKE rejected','application_ids':ids,'expected_revisions':values})
    assert r.status_code==422,r.text
    assert any(str(ids[invalid_position]) in [str(i) for i in e['loc']] for e in r.json()['detail'])
    assert snapshot()==before

@pytest.mark.parametrize('shape',['missing','empty','incomplete'])
def test_missing_bulk_precondition_is_428(client,pair,shape):
    body={'role':'province','decision':'hold','application_ids':list(pair)}
    if shape!='missing':body['expected_revisions']={'empty':{},'incomplete':{str(pair[0]):1}}[shape]
    before=snapshot();r=client.post('/api/officer/applications/decisions',json=body)
    assert r.status_code==428 and r.json()['detail']['code']=='REVIEW_REVISION_REQUIRED';assert snapshot()==before

@pytest.mark.parametrize('value',[None,[],[1],True,'1',1.5])
def test_bulk_map_format_is_422(client,pair,value):
    before=snapshot();r=client.post('/api/officer/applications/decisions',json={'decision':'hold','application_ids':list(pair),'expected_revisions':value})
    assert r.status_code==422;assert snapshot()==before

@pytest.mark.parametrize('token',[2,MAX_EXPECTED_REVISION])
def test_valid_range_stale_token_is_409_not_422(client,pair,token):
    before=snapshot();r=client.post('/api/officer/applications/decisions',json={'role':'province','decision':'hold','application_ids':list(pair),'expected_revisions':{str(pair[0]):1,str(pair[1]):token}})
    assert r.status_code==409 and r.json()['detail']['code']=='REVIEW_REVISION_CONFLICT';assert snapshot()==before

def test_valid_bulk_increments_each_row_once_preserves_engine_fields(client,pair):
    before=snapshot();r=client.post('/api/officer/applications/decisions',json={'role':'province','decision':'hold','memo':'FAKE accepted','application_ids':list(pair),'expected_revisions':{str(i):1 for i in pair}})
    assert r.status_code==200,r.text
    rows,apps=snapshot()
    for i,row in enumerate(rows):
        assert row['revision']==2 and row['officer_memo']=='FAKE accepted' and row['final_status']==before[0][i]['final_status']
        assert row['officer_decision']=='hold' and apps[i]['status']=='reviewing'
