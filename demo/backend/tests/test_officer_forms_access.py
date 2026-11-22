"""Synthetic submitted-form reads; real owner/officer guards and PDF rendering."""
from hashlib import sha256

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from demo.backend import models, officer_auth
from demo.backend.api import common
from demo.backend.main import app
from demo.backend.tests.test_access_control import security, new_application, login
from demo.backend.tests.security_support import claim_synthetic_application
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_eligibility_blockers import ready


def submitted(owner):
    application = ready(make_application(premium=1))
    claim_synthetic_application(owner, application.id)
    root = common.STORAGE
    root.mkdir(parents=True, exist_ok=True)
    with models.get_session() as session:
        for document in session.exec(select(models.Document).where(models.Document.application_id == application.id)).all():
            path = root / f'synthetic-{document.id}.pdf'
            with fitz.open() as pdf:
                pdf.new_page().insert_text((30, 30), 'SYNTHETIC ORIGINAL')
                path.write_bytes(pdf.tobytes())
            document.file_path = str(path.relative_to(root.parent))
            session.add(document)
        session.commit()
    assert owner.get(f'/api/applications/{application.id}/final-check').json()['can_submit']
    response = owner.post(f'/api/applications/{application.id}/submit')
    assert response.status_code == 200, response.text
    return application.id


def officer_client():
    client = TestClient(app)
    assert login(client).status_code == 200
    assert [c.name for c in client.cookies.jar] == ['officer_session']
    return client


def pdf_text(response):
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['content-disposition'].startswith('inline;')
    assert 'no-store' in response.headers['cache-control']
    with fitz.open(stream=response.content, filetype='pdf') as pdf:
        assert len(pdf) > 0
        return ''.join(page.get_text() for page in pdf)


def fingerprint():
    with models.get_session() as session:
        rows = {m.__name__: [row.model_dump(mode='json') for row in session.exec(select(m)).all()]
                for m in (models.Application, models.Document, models.Consent, models.Review)}
    import json
    return (sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
            {str(p.relative_to(common.STORAGE)): sha256(p.read_bytes()).hexdigest()
             for p in common.STORAGE.rglob('*') if p.is_file()})


def test_phase2_officer_only_detail_link_opens_after_real_submission(security):
    aid = submitted(security)
    officer = officer_client()
    assert officer.get('/api/officer/applications').status_code == 200
    detail = officer.get(f'/api/officer/applications/{aid}')
    assert detail.status_code == 200
    link = detail.json()['forms'][0]
    assert link['form_no'] == '서식2'
    # Before the fix, the exact API-supplied Phase 2 link returns owner-only 403.
    pdf_text(officer.get(link['file_url']))


@pytest.mark.parametrize('status', ['draft', 'submitted', 'reviewing', 'decided'])
def test_form_visibility_matches_submitted_workflow(security, status):
    aid = submitted(security)
    with models.get_session() as session:
        row = session.get(models.Application, aid)
        row.status = status
        session.add(row)
        session.commit()
    officer = officer_client()
    response = officer.get(f'/api/officer/applications/{aid}/forms/서식1.pdf')
    if status == 'draft':
        assert response.status_code == 404
    else:
        assert '가상신청' in pdf_text(response)
    # Existing owner view remains available, including draft previews.
    pdf_text(security.get(f'/api/applications/{aid}/forms/서식1.pdf'))


@pytest.mark.parametrize('actor', ['anonymous', 'other-owner', 'owner', 'forged-role', 'forged-session', 'expired', 'revoked'])
def test_only_current_officer_session_authorizes_officer_form(security, monkeypatch, actor):
    aid = submitted(security)
    client = TestClient(app)
    if actor == 'other-owner':
        new_application(client)
    elif actor == 'owner':
        client.cookies.update(security.cookies)
    elif actor == 'forged-session':
        client.cookies.set('officer_session', 'synthetic-forged', path='/api')
    elif actor in {'expired', 'revoked'}:
        assert login(client).status_code == 200
        if actor == 'expired':
            now = officer_auth.time.time()
            monkeypatch.setattr(officer_auth.time, 'time', lambda: now + officer_auth.SESSION_SECONDS + 1)
        else:
            token = client.cookies.get('officer_session')
            assert client.post('/api/officer/logout').status_code == 200
            client.cookies.set('officer_session', token, path='/api')
    response = client.get(f'/api/officer/applications/{aid}/forms/서식1.pdf?role=province',
                          headers={'Authorization': 'Bearer province'} if actor == 'forged-role' else {})
    assert response.status_code == 401
    assert response.headers['cache-control'] == 'private, no-store'


@pytest.mark.parametrize('form', ['서식0', 'job_application', 'job_consent', 'written', 'signature-scan', '99999'])
def test_missing_or_other_policy_form_stays_closed(security, form):
    aid = submitted(security)
    response = officer_client().get(f'/api/officer/applications/{aid}/forms/{form}.pdf')
    assert response.status_code == 404
    assert 'no-store' in response.headers['cache-control']


@pytest.mark.parametrize('alias', ['99999999', '0', '-1', 'abc', '1.5'])
def test_invalid_or_missing_application_never_returns_a_file(security, alias):
    submitted(security)
    response = officer_client().get(f'/api/officer/applications/{alias}/forms/서식1.pdf')
    assert response.status_code in {404, 422}


def test_paper_consent_and_owner_archive_boundaries(security):
    aid = submitted(security)
    officer = officer_client()
    with models.get_session() as session:
        row = session.get(models.Application, aid)
        row.doc_context_json = {**row.doc_context_json, 'paper_forms': {'서식5': True}}
        session.add(row)
        session.commit()
    detail = officer.get(f'/api/officer/applications/{aid}').json()
    assert '서식5' not in [f['form_no'] for f in detail['forms']]
    assert officer.get(f'/api/officer/applications/{aid}/forms/서식5.pdf').status_code == 404
    for suffix in ['', '/forms', '/forms/서식1.pdf', '/forms/files/written.pdf', '/forms/signature-scan.png', '/forms/templates/서식1.pdf']:
        assert officer.get(f'/api/applications/{aid}{suffix}').status_code == 403
    for method, suffix in [('PATCH', ''), ('POST', '/submit'), ('DELETE', '/forms/signature-scan')]:
        assert officer.request(method, f'/api/applications/{aid}{suffix}', json={}).status_code == 403
    assert security.get(f'/api/applications/{aid}/forms/files/written.pdf').status_code == 200
    for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        assert officer.request(method, f'/api/officer/applications/{aid}/forms/서식1.pdf').status_code == 405


def test_reads_are_bound_to_path_application_and_never_mutate(security):
    aid = submitted(security)
    other = new_application(security)
    assert security.patch(f'/api/applications/{other}', json={'form1': {'name': '다른합성신청'}}).status_code == 200
    with models.get_session() as session:
        row = session.get(models.Application, other)
        row.status = models.STATUS_SUBMITTED
        session.add(row)
        session.commit()
    officer = officer_client()
    # Materialize detail once; the read under test must not create any rows/files.
    detail = officer.get(f'/api/officer/applications/{aid}').json()
    before = fingerprint()
    for form in detail['forms']:
        pdf_text(officer.get(form['file_url']))
    first = pdf_text(officer.get(f'/api/officer/applications/{aid}/forms/서식1.pdf?application_id={other}'))
    second = pdf_text(officer.get(f'/api/officer/applications/{other}/forms/서식1.pdf?application_id={aid}'))
    assert '가상신청' in first and '다른합성신청' not in first
    assert '다른합성신청' in second and '가상신청' not in second
    for alias in [f'+{aid}', f'0{aid}']:
        assert '가상신청' in pdf_text(officer.get(f'/api/officer/applications/{alias}/forms/서식1.pdf'))
    assert before == fingerprint()
    # Another owner still cannot guess a protected applicant PDF URL.
    stranger = TestClient(app)
    new_application(stranger)
    assert stranger.get(f'/api/applications/{aid}/forms/서식1.pdf').status_code == 403
