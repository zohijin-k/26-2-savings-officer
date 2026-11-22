"""Synthetic date provenance regressions; no real documents or network OCR."""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from demo.backend.api.common import checklist_from_inputs, document_fact
from demo.backend.engine_adapter import (
    engine_check_single_document, run_pipeline, to_engine_applicant, to_engine_documents,
)
from demo.backend.models import Document
from demo.backend.ocr import read_document
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.criteria import default_criteria, issue_bounds
from demo.backend.rules.doc_check import check_document, to_engine_document, to_engine_spec
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.programs import get_program
from demo.backend.rules.required_docs import ApplicantDocInput, DocRequirement
from demo.backend.rules.subsidy import Selection
from demo.backend.tests.run_p16_job_docs_scenarios import make_text_pdf

ISSUE = date(2026, 11, 22)
EVENT = date(2026, 11, 1)


def requirement():
    return next(req for req in checklist_from_inputs(
        get_program('job_package'),
        ApplicantDocInput(subsidy_selections=[Selection(item_type='interview', count=1)]),
        default_criteria('job_package'), ISSUE,
    ) if req.slot_key == 'interview_1_confirmation')


def fact(req, ocr, declared=ISSUE, status='PASS'):
    # Use the real persisted OCR representation and production deserializer.
    from demo.backend.api.documents import _ocr_json
    return document_fact(Document(id=1, application_id=1, slot_key=req.slot_key,
        file_path='synthetic.pdf', file_format='pdf', doc_type=str(req.doc_type),
        expected_doc_type=str(req.doc_type), ocr_json=_ocr_json(ocr),
        declared_issue_date=declared, stage1_status=status))


def synthetic_pdf(tmp_path, issue='2026-11-22', *, extra=()):
    lines = ['면접확인서', '성명 합성가상', '생년월일 2000-05-15',
             '회사명 합성회사(SEED)', '면접일 2026-11-01']
    if issue is not None:
        lines.append(f'발급일자 {issue}')
    return make_text_pdf(tmp_path / 'FAKE-date-parity.pdf',
                         [*lines, *extra, '면접 참석 사실을 확인합니다.'])


def test_phase2_explicit_issue_is_read_and_not_replaced_by_interview(tmp_path):
    req = requirement()
    ocr = read_document(str(synthetic_pdf(tmp_path)), req.doc_type)
    assert ocr.fields['면접일'] == EVENT.isoformat()
    assert ocr.fields.get('발급일') == ISSUE.isoformat()
    upload = check_document(req, ocr, ISSUE, 'pdf')
    final_doc = to_engine_documents([fact(req, ocr)], [req])[0]
    assert final_doc.issue_date == to_engine_document(req, ocr, ISSUE, 'pdf').issue_date == ISSUE
    assert upload.status == 'PASS'
    assert not engine_check_single_document(final_doc, to_engine_spec(req))


@pytest.mark.parametrize('declared', [ISSUE - timedelta(days=1), ISSUE, ISSUE + timedelta(days=1)])
def test_real_explicit_issue_declaration_mismatch_is_preserved(tmp_path, declared):
    req = requirement()
    ocr = read_document(str(synthetic_pdf(tmp_path)), req.doc_type)
    upload = check_document(req, ocr, declared, 'pdf')
    final_doc = to_engine_documents([fact(req, ocr, declared)], [req])[0]
    final_codes = {x.code.value for x in engine_check_single_document(final_doc, to_engine_spec(req))}
    assert ('DECLARED_DATE_MISMATCH' in upload.codes) == (declared != ISSUE)
    assert ('DECLARED_DATE_MISMATCH' in final_codes) == (declared != ISSUE)


@pytest.mark.parametrize('issue', [None, '', '2026-02-30', '2026-11-2?', '2026-11-22 extra'])
def test_unread_issue_is_review_without_using_legacy_event_alias(issue):
    req = requirement()
    fields = {'성명': '합성가상', '회사명': '합성회사', '면접일': EVENT.isoformat()}
    if issue is not None:
        fields['발급일'] = issue
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    issue_date=EVENT, fields=fields, tier='localocr', engine='pdftext')
    upload = check_document(req, ocr, ISSUE, 'pdf')
    assert upload.status == 'NEEDS_REVIEW'
    assert all(f.severity != 'FAIL' for f in upload.findings)
    final_doc = to_engine_documents([fact(req, ocr)], [req])[0]
    assert final_doc.issue_date is None
    assert final_doc.ocr_confidence < .85
    assert 'DECLARED_DATE_MISMATCH' not in {
        f.code.value for f in engine_check_single_document(final_doc, to_engine_spec(req))}


@pytest.mark.parametrize('basis,field,value', [
    ('issue_date', '발급일', '2026-11-22'), ('interview_date', '면접일', '2026-11-01'),
    ('payment_date', '결제일', '2026-10-31'), ('exam_date', '응시일', '2026-02-28'),
    ('none', None, None),
])
def test_same_slot_uses_same_policy_field_after_db_roundtrip(basis, field, value):
    req = replace(requirement(), date_basis=basis, check_declared_date=basis != 'none')
    fields = {'발급일': '2026-11-22', '면접일': '2026-11-01', '결제일': '2026-10-31', '응시일': '2026-02-28'}
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    issue_date=EVENT, fields=fields, tier='localocr', engine='pdftext')
    before = to_engine_document(req, ocr, ISSUE, 'pdf', basis)
    after = to_engine_documents([fact(req, ocr)], [req])[0]
    assert before.issue_date == after.issue_date == (date.fromisoformat(value) if field else None)


@pytest.mark.parametrize('value', ['2026-11-22T00:00:00+09:00', '2026-11-21T15:00:00Z',
                                 '20261122', '2026-W47-7', '2026-11-22?', ' 2026-11-22 '])
def test_date_only_evidence_does_not_truncate_or_timezone_shift(value):
    req = requirement()
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    issue_date=EVENT, fields={'발급일': value}, tier='localocr', engine='own')
    assert to_engine_document(req, ocr, ISSUE, 'pdf').issue_date is None
    assert check_document(req, ocr, ISSUE, 'pdf').status == 'NEEDS_REVIEW'


@pytest.mark.parametrize('day', ['2025-12-31', '2026-01-01', '2026-01-02',
                                '2026-10-31', '2026-11-01', '2024-02-29'])
def test_minimum_date_is_inclusive_and_calendar_dates_survive(day):
    req = requirement()
    issued = date.fromisoformat(day)
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    fields={'발급일': day}, tier='localocr', engine='pdftext')
    upload = check_document(req, ocr, issued, 'pdf')
    final_doc = to_engine_documents([fact(req, ocr, issued)], [req])[0]
    expected = issued < req.min_issue_date
    assert ('DOCUMENT_ISSUED_TOO_EARLY' in upload.codes) == expected
    assert ('DOCUMENT_ISSUED_TOO_EARLY' in {f.code.value for f in
        engine_check_single_document(final_doc, to_engine_spec(req))}) == expected


def test_repeated_types_keep_slot_specific_dates_and_cannot_hide_earlier_failure():
    first = replace(requirement(), slot_key='interview_1_confirmation', date_basis='issue_date')
    second = replace(first, slot_key='interview_2_confirmation', date_basis='interview_date')
    ocr = OcrResult(detected_doc_type=first.doc_type, confidence=.95, image_quality=1,
                    issue_date=ISSUE, fields={'발급일': '2026-11-22', '면접일': '2026-11-01'},
                    tier='localocr', engine='pdftext')
    rows = [fact(first, ocr, EVENT), fact(second, ocr, EVENT)]
    docs = to_engine_documents(rows, [first, second])
    assert [d.issue_date for d in docs] == [ISSUE, EVENT]
    applicant = to_engine_applicant(application_no='SYNTHETIC-DATES', name='합성가상',
        birth_date=date(2000, 5, 15), residence_region='전주시', program=get_program('job_package'),
        income_percent=None)
    result = run_pipeline(applicant, docs, [first, second])
    assert result.stage1.status.value == 'FAIL'
    assert 'DECLARED_DATE_MISMATCH' in {f.code.value for f in result.stage1.findings}


def test_low_confidence_mismatch_remains_review():
    req = requirement()
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.6, image_quality=1,
                    issue_date=ISSUE, fields={'발급일': ISSUE.isoformat()}, tier='localocr', engine='own')
    assert check_document(req, ocr, EVENT, 'pdf').status == 'NEEDS_REVIEW'
    doc = to_engine_documents([fact(req, ocr, EVENT, 'NEEDS_REVIEW')], [req])[0]
    assert 'DECLARED_DATE_MISMATCH' not in {f.code.value for f in engine_check_single_document(doc, to_engine_spec(req))}


def test_no_date_policy_does_not_manufacture_missing_date_review():
    req = replace(requirement(), date_basis='none', check_declared_date=False,
                  min_issue_date=None, max_issue_date=None)
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    fields={}, tier='localocr', engine='pdftext')
    assert check_document(req, ocr, None, 'pdf').status == 'PASS'


def test_existing_within_days_bounds_include_both_ends():
    criteria = default_criteria('job_package')
    criteria['document_issue_rules']['resident_abstract'] = {'mode': 'within_days', 'days': 30}
    assert issue_bounds(criteria, 'resident_abstract', ISSUE) == (date(2026, 10, 23), ISSUE)


def test_conflicting_explicit_issue_dates_are_not_arbitrarily_selected(tmp_path):
    req = requirement()
    ocr = read_document(str(synthetic_pdf(tmp_path, extra=['발급일 2026-11-21'])), req.doc_type)
    assert '발급일' not in ocr.fields
    assert check_document(req, ocr, ISSUE, 'pdf').status == 'NEEDS_REVIEW'


def test_confirmation_and_birth_are_not_issue_evidence(tmp_path):
    req = requirement()
    path = make_text_pdf(tmp_path / 'FAKE-confirm-only.pdf', ['면접확인서', '성명 합성가상',
        '생년월일 2000-05-15', '회사명 합성회사', '면접일 2026-11-01',
        '면접 참석 사실을 확인합니다.', '2026년 11월 22일'])
    ocr = read_document(str(path), req.doc_type)
    assert ocr.fields['확인일'] == ISSUE.isoformat()
    assert '발급일' not in ocr.fields
    assert check_document(req, ocr, ISSUE, 'pdf').status == 'NEEDS_REVIEW'


@pytest.mark.parametrize('value', ['2026-02-30', '2026-11-22T00:00:00+09:00',
                                 '20261122', '2026-W47-7', '2026-11-22?'])
def test_api_rejects_non_calendar_date_contract(value):
    from fastapi import HTTPException
    from demo.backend.api.documents import _parse_date
    with pytest.raises(HTTPException) as caught:
        _parse_date(value)
    assert caught.value.status_code == 400


def test_legacy_type_only_model_constructor_order_remains_compatible():
    from engine.models import RequiredDocumentSpec
    spec = RequiredDocumentSpec('synthetic', True, False, None, None, True)
    assert spec.check_declared_date is True
    assert spec.slot_key is None


# The existing fixture creates a fresh synthetic DB/storage and authenticates via login.
from demo.backend.tests.test_portal_uploads import client


@pytest.mark.parametrize('printed,declared,expected', [
    ('2026-11-22', '2026-11-22', 'PASS'),
    ('2026-11-22', '2026-11-21', 'FAIL'),
    (None, '2026-11-22', 'NEEDS_REVIEW'),
])
def test_actual_upload_final_check_submit_and_officer_detail_dates(client, tmp_path, monkeypatch,
                                                                  printed, declared, expected):
    from demo.backend import models
    from demo.backend.api import common, forms
    from demo.backend.tests.run_p5_scenarios import create_job_application, S10_SELECTION, S10_UPLOADS
    from sqlmodel import select
    monkeypatch.setattr(forms, 'STORAGE', common.STORAGE)
    from demo.backend.tests.security_support import authenticate_officer
    authenticate_officer(client, monkeypatch)
    aid = create_job_application(client, selections=S10_SELECTION, uploads=S10_UPLOADS)
    lines = ['면접확인서', '성명 김청년', '생년월일 1999-04-10',
             '회사명 합성회사(SEED)', '면접일 2026-11-01']
    if printed:
        lines.append(f'발급일자 {printed}')
    path = make_text_pdf(tmp_path / 'FAKE-api-interview.pdf', [*lines, '면접 참석 사실을 확인합니다.'])
    response = client.post(f'/api/applications/{aid}/documents',
        data={'slot_key': 'interview_1_confirmation', 'declared_issue_date': declared},
        files={'file': ('FAKE-api-interview.pdf', path.read_bytes(), 'application/pdf')})
    assert response.status_code == 200, response.text
    upload = response.json()
    with models.get_session() as session:
        saved = session.exec(select(models.Document).where(models.Document.id == upload['document_id'])).one()
        assert saved.declared_issue_date.isoformat() == declared
        assert saved.stage1_status == expected
        assert saved.ocr_json['fields'].get('발급일') == printed
    readiness = client.get(f'/api/applications/{aid}/final-check')
    assert readiness.status_code == 200
    result = client.post(f'/api/applications/{aid}/submit')
    # Officer's existing public projection excludes date findings; stored internal FAIL survives.
    assert readiness.json()['can_submit'] is True, readiness.text
    assert result.status_code == 200, result.text
    detail = client.get(f'/api/officer/applications/{aid}')
    assert detail.status_code == 200
    with models.get_session() as session:
        review = session.exec(select(models.Review).where(models.Review.application_id == aid)).one()
        assert ('DECLARED_DATE_MISMATCH' in {r['code'] for r in review.review_payload_json['reasons']}) == (expected == 'FAIL')
        assert review.stage1_status == expected, review.review_payload_json["reasons"]
        if expected == 'NEEDS_REVIEW':
            assert review.final_status != 'PASS'


@pytest.mark.parametrize('actual', [date(2025,12,31), date(2026,11,23)])
def test_low_confidence_outside_bounds_stays_review_in_upload_and_final(actual):
    req = replace(requirement(), max_issue_date=ISSUE)
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.6, image_quality=1,
                    fields={'발급일': actual.isoformat()}, issue_date=actual, tier='localocr', engine='own')
    assert check_document(req, ocr, ISSUE, 'pdf').status == 'NEEDS_REVIEW'
    applicant = to_engine_applicant(application_no='SYNTHETIC-UNCERTAIN', name='합성가상',
        birth_date=date(2000,5,15), residence_region='전주시', program=get_program('job_package'), income_percent=None)
    result = run_pipeline(applicant, to_engine_documents([fact(req,ocr,ISSUE,'NEEDS_REVIEW')],[req]), [req])
    assert result.stage1.status.value == 'NEEDS_REVIEW'


@pytest.mark.parametrize('offset,expected', [(-1,False),(0,False),(1,True)])
def test_maximum_date_inclusive_after_db_roundtrip(offset,expected):
    req = replace(requirement(), max_issue_date=ISSUE)
    day = ISSUE + timedelta(days=offset)
    ocr = OcrResult(detected_doc_type=req.doc_type, confidence=.95, image_quality=1,
                    fields={'발급일':day.isoformat()}, issue_date=day, tier='localocr', engine='pdftext')
    upload = check_document(req,ocr,day,'pdf')
    converted = to_engine_documents([fact(req,ocr,day)],[req])[0]
    assert ('DOCUMENT_ISSUED_AFTER_APPLICATION' in upload.codes) == expected
    assert ('DOCUMENT_ISSUED_AFTER_APPLICATION' in {f.code.value for f in
        engine_check_single_document(converted,to_engine_spec(req))}) == expected



def test_generated_electronic_consent_retains_its_authenticated_event_date():
    from demo.backend.engine_adapter import electronic_consent_row
    req = DocRequirement('admin_info_consent', DocType.ADMIN_INFO_CONSENT, '전자동의',
        upload=False, requires_signature=True, check_declared_date=False,
        min_issue_date=date(2026,3,3))
    row = electronic_consent_row(ISSUE, 'synthetic-signature.png')
    doc = to_engine_documents([row], [req])[0]
    assert doc.issue_date == ISSUE
    assert doc.ocr_confidence == 1
    assert not engine_check_single_document(doc, to_engine_spec(req))


def test_explicit_issue_below_confirmation_preserves_existing_chronology_guard(tmp_path):
    req = requirement()
    path = make_text_pdf(tmp_path / 'FAKE-chronology.pdf', ['면접확인서', '성명 합성가상',
        '생년월일 2000-05-15', '회사명 합성회사', '면접일 2026-11-02',
        '면접 참석 사실을 확인합니다.', '발급일자 2026-11-01'])
    ocr = read_document(str(path), req.doc_type)
    assert ocr.fields.get('발급일') == '2026-11-01'
    assert check_document(req, ocr, date(2026,11,1), 'pdf').status == 'NEEDS_REVIEW'
