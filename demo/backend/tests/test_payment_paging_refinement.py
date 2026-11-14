"""Refinement of payment-only paging; old fixtures and expectations untouched."""
import json
import pytest
from demo.backend.tests.test_payment_paging import pages,assess,UNCERTAIN
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.test_payment_failure_certainty import requirement
from demo.backend.rules.doc_check import check_document
from demo.backend.ocr.localocr import _from_nhis
from engine_v2.extractors import nhis_payment
from engine_v2.schemas.models import DocType as V2

@pytest.mark.parametrize('text',[False,True])
@pytest.mark.parametrize('marker,confidence',[(None,1),('1/',1),('1/2',.2),('1/1',1)])
def test_confirmed_period_table_totals_and_issue_can_exclude_only_paging_review(text,marker,confidence):
    _,verdict=assess(pages(marker,confidence,text=text))
    assert verdict.status=='PASS'

@pytest.mark.parametrize('text',[False,True])
@pytest.mark.parametrize('marker',['1/1','1/2',None])
def test_complete_marker_never_substitutes_for_complete_table(text,marker):
    _,verdict=assess(pages(marker,broken_table=True,text=text))
    assert verdict.status==('FAIL' if marker=='1/2' else 'NEEDS_REVIEW')
    assert ('PAGES_INCOMPLETE' if marker=='1/2' else UNCERTAIN) in verdict.codes

@pytest.mark.parametrize('text',[False,True])
def test_missing_final_issue_page_fails_when_counter_is_read(text):
    p=pages('1/2',text=text)
    p[0][1].words[:]=[w for w in p[0][1].words if '2026' not in w.text]
    _,verdict=assess(p)
    assert verdict.status=='FAIL'
    assert 'PAGES_INCOMPLETE' in verdict.codes

@pytest.mark.parametrize('text',[False,True])
@pytest.mark.parametrize('marker',[None,'1/2'])
def test_unread_final_issue_information_cannot_be_waived_by_complete_table(text,marker):
    p=pages(marker,text=text)
    p[0][1].words[:]=[w for w in p[0][1].words if '2026' not in w.text]
    _,verdict=assess(p)
    assert verdict.status==('FAIL' if marker=='1/2' else 'NEEDS_REVIEW')

@pytest.mark.parametrize('text',[False,True])
def test_reliable_excess_fails_against_current_slot_file(text):
    _,verdict=assess(pages('1/2',text=text))
    assert verdict.status=='FAIL'
    assert 'PAGES_INCOMPLETE' in verdict.codes

@pytest.mark.parametrize('marker',['1/2','2/2'])
def test_each_replacement_file_must_contain_all_pages(marker):
    _,verdict=assess(pages(marker))
    assert verdict.status=='FAIL'
    assert 'PAGES_INCOMPLETE' in verdict.codes

@pytest.mark.parametrize('text',[False,True])
def test_uncertain_period_even_with_matching_table_keeps_review(text):
    p=pages(None,text=text)
    next(w for w in p[0][1].words if '납부내역' in w.text).confidence=.2
    _,verdict=assess(p)
    assert verdict.status=='NEEDS_REVIEW'
    assert UNCERTAIN in verdict.codes

@pytest.mark.parametrize('text',[False,True])
def test_conflicting_total_markers_keep_review_even_with_table(text):
    p=pages('1/2',text=text)
    other=pages('2/3',text=text)[0]
    other[0].page=1
    p.append(other)
    _,verdict=assess(p)
    assert verdict.status=='NEEDS_REVIEW'
    assert 'PAGES_INCOMPLETE' not in verdict.codes

@pytest.mark.parametrize('text',[False,True])
def test_missing_printed_total_cannot_use_vacuous_arithmetic_pass(text):
    p=pages(None,text=text);words=p[0][1].words
    sum_y=next(w.bbox_px[1] for w in words if w.text=='합계')
    words[:]=[w for w in words if w.bbox_px[1]!=sum_y]
    _,verdict=assess(p)
    assert verdict.status=='NEEDS_REVIEW'
    assert UNCERTAIN in verdict.codes


@pytest.mark.parametrize('value',['not-an-amount','100001','-1'])
def test_changed_monthly_values_cannot_reuse_old_arithmetic_proof(value):
    ocr,_=assess(pages(None))
    monthly=json.loads(ocr.fields['월별고지금액'])
    monthly['2025-10']=value
    ocr.fields['월별고지금액']=json.dumps(monthly)
    verdict=check_document(requirement(),ocr)
    assert verdict.status=='NEEDS_REVIEW'
    assert UNCERTAIN in verdict.codes


def test_changed_issue_date_cannot_reuse_old_source_read_proof():
    from datetime import date
    ocr,_=assess(pages(None))
    ocr.issue_date=date(2026,3,4)
    ocr.fields['발급일']='2026-03-04'
    assert UNCERTAIN in check_document(requirement(),ocr).codes


@pytest.mark.parametrize('image',[False,True])
@pytest.mark.parametrize('marker,broken,expected',[(None,False,'PASS'),('1/2',False,'FAIL'),('1/1',True,'NEEDS_REVIEW')])
def test_real_pdf_routes_share_payment_completeness_policy(tmp_path,monkeypatch,image,marker,broken,expected):
    from demo.backend.ocr import read_document
    from demo.backend.rules.doc_types import DocType
    from demo.backend.tests.test_p2_nhis_uploads import image_pdf,use_own_words
    from engine_v2.tests import p2_payment_samples as base
    from engine_v2.tests.test_income_payment_evidence import _text_pdf
    cells,size=base.payment()
    if broken:
        cells=[c for c in cells if not (c[4]=='소득월액' and c[0]>1700)]
    if marker:
        cells.append(base.cell(size[0]*.84,size[1]*.93,size[0]*.94,size[1]*.93+28,marker,1))
    path=tmp_path/'FAKE-policy.pdf'
    if image:
        use_own_words(monkeypatch,cells,size)
        image_pdf(path,size)
    else:
        monkeypatch.setenv('ENGINE_V2_OCR','off')
        _text_pdf(path,cells,size)
    result=read_document(str(path),DocType.NHIS_PAYMENT)
    verdict=check_document(requirement(),result)
    assert verdict.status==expected
    assert ('PAGES_INCOMPLETE' in verdict.codes)==(expected=='FAIL')


def test_second_upload_replaces_first_and_remaining_file_controls_paging(client,tmp_path,monkeypatch):
    from demo.backend.tests.test_p2_nhis_uploads import image_pdf,use_own_words
    from demo.backend.tests.test_portal_uploads import new_app,upload
    from engine_v2.tests import p2_payment_samples as base
    aid=new_app(client,name=base.NAME,birth=base.BIRTH)
    for index,marker in enumerate(['1/2','2/2']):
        cells,size=base.payment()
        cells.append(base.cell(size[0]*.84,35,size[0]*.94,65,marker,1))
        use_own_words(monkeypatch,cells,size)
        path=image_pdf(tmp_path/f'FAKE-part-{index}.pdf',size)
        response,stored=upload(client,aid,path,'nhis_payment')
        assert response['status']=='FAIL'
        assert any(f['code']=='PAGES_INCOMPLETE' and f['severity']=='FAIL' for f in response['findings'])
        listed=client.get(f'/api/applications/{aid}/documents').json()
        payment=[r for r in listed if r['slot_key']=='nhis_payment']
        assert len(payment)==1
        evidence=json.loads(stored['fields']['납부쪽표기자료'])
        assert evidence['markers']==[[index+1,2]]
        assert stored['page_count']==1



@pytest.mark.parametrize('key',['합계자료','납부총액','월별장기요양보험료'])
def test_changed_source_financial_fields_cannot_reuse_table_proof(key):
    ocr,_=assess(pages(None))
    ocr.fields[key]='not-a-source-financial-value'
    verdict=check_document(requirement(),ocr)
    assert verdict.status=='NEEDS_REVIEW'
    assert UNCERTAIN in verdict.codes
