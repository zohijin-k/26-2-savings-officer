"""Synthetic HTTP projections keep diagnostics in officer evidence only."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from demo.backend import models
from demo.backend.api import common, officer
from demo.backend.main import app
from demo.backend.tests.test_access_control import security

PUBLIC_KEYS = {'document_id', 'slot_key', 'file_name', 'file_format', 'file_url',
               'expected_doc_type', 'detected_doc_type', 'declared_issue_date',
               'status', 'findings', 'extracted', 'page_index', 'uploaded_at'}

@pytest.mark.parametrize('state', ['PASS', 'FAIL', 'NEEDS_REVIEW', None])
@pytest.mark.parametrize('program', ['job_package', 'double_savings'])
def test_owner_views_exclude_telemetry_keep_evidence_and_reject_other_owner(security, state, program):
    created = security.post('/api/applications', json={'program_code': program})
    assert created.status_code == 200, created.text
    aid = created.json()['id']
    ocr = {'confidence': .37, 'elapsed_ms': 817, 'fields': {'발급일': '2026-11-22',
           '건강보험료': 'SYNTHETIC_INTERNAL', '판독검증실패': 'SYNTHETIC_INTERNAL'},
           'tier': 'synthetic', 'engine': 'synthetic'}
    findings = [{'code': 'LOW_OCR_CONFIDENCE', 'severity': 'NEEDS_REVIEW',
                 'message': '담당자가 확인합니다.', 'detail': 'SYNTHETIC_PRIVATE_DETAIL'}]
    with models.get_session() as session:
        row = models.Document(application_id=aid, slot_key='resident_abstract',
            file_path='synthetic.pdf', file_format='pdf', stage1_status=state,
            ocr_json=deepcopy(ocr), findings_json=deepcopy(findings))
        session.add(row); session.commit(); session.refresh(row)
        did = row.id
    for phase in ['draft', 'submitted']:
        if phase == 'submitted':
            # Historical submitted-state projection, not a claim of successful submission.
            with models.get_session() as session:
                application = session.get(models.Application, aid)
                application.status = models.STATUS_SUBMITTED
                session.add(application); session.commit()
        for tail in ['documents', 'required-documents', 'final-check', 'status']:
            path = f'/api/applications/{aid}/{tail}'
            response = security.get(path)
            assert response.status_code == 200, response.text
            body = response.json()
            if tail == 'documents': rows = body
            elif tail == 'required-documents':
                rows = [d for item in body['items'] for d in item['documents']] + body['unassigned']
            else: rows = body['documents']
            assert rows
            for shown in rows:
                assert set(shown) == PUBLIC_KEYS
                assert 'SYNTHETIC_INTERNAL' not in str(shown)
                assert 'SYNTHETIC_PRIVATE_DETAIL' not in str(shown)
            outsider = TestClient(app)
            assert outsider.get(path).status_code == 403
            outsider.post('/api/applications', json={'program_code': 'job_package'})
            assert outsider.get(path).status_code == 403
    with models.get_session() as session:
        stored = session.get(models.Document, did)
        assert stored.ocr_json == ocr and stored.findings_json == findings
        internal = officer._document_view(stored, {})
        assert internal['ocr_confidence'] == .37
        assert internal['findings'] == [{**findings[0], 'title': '자동 판독 신뢰도 낮음'}]
        assert internal['extracted']['건강보험료'] == 'SYNTHETIC_INTERNAL'

@pytest.mark.parametrize('program', ['job_package', 'double_savings'])
def test_upload_response_excludes_telemetry_without_changing_stored_diagnostics(security, monkeypatch, program):
    import pymupdf
    from demo.backend.api import documents
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_check import CheckResult
    from demo.backend.rules.doc_types import DocType
    from demo.backend.tests.run_p6_scenarios import _stored_ocr
    created = security.post('/api/applications', json={'program_code': program})
    assert created.status_code == 200, created.text
    aid = created.json()['id']
    # Explicit synthetic OCR stub: this test verifies HTTP projection, not OCR accuracy.
    read = OcrResult(DocType.RESIDENT_ABSTRACT, .37, fields={'발급일': '2026-11-22'}, elapsed_ms=817)
    monkeypatch.setattr(documents, 'assess_upload', lambda *a, **kw: (read, CheckResult('NEEDS_REVIEW', [])))
    monkeypatch.setattr(documents, 'read_document', lambda *a, **kw: read)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40,40), 'SYNTHETIC ONLY')
        data = pdf.tobytes()
    result = security.post(f'/api/applications/{aid}/documents',
        data={'slot_key': 'resident_abstract', 'declared_issue_date': '2026-11-22'},
        files={'file': ('synthetic.pdf', data, 'application/pdf')})
    assert result.status_code == 200, result.text
    shown = result.json()
    assert set(shown) == PUBLIC_KEYS
    internal = _stored_ocr(shown)
    assert internal['confidence'] == .37 and internal['elapsed_ms'] == 817
