"""Synthetic contracts for PR35's response-only officer reason labels."""
from copy import deepcopy

import pytest
from sqlmodel import select

from demo.backend import models
from demo.backend.api.common import document_dict
from demo.backend.officer_summary import readable_reason
from demo.backend.tests.security_support import authenticate_officer, claim_synthetic_application
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_portal_uploads import client


@pytest.mark.parametrize("source,expected", [
    ({"code": "MISSING_SIGNATURE", "severity": "FAIL", "message": "서명을 확인하세요."},
     {"code": "MISSING_SIGNATURE", "severity": "FAIL", "message": "서명을 확인하세요.", "title": "서명 없음"}),
    ({"code": "MISSING_SIGNATURE", "message": "MISSING_SIGNATURE (NEEDS_REVIEW)",
      "how_to_fix": "MISSING_SIGNATURE 확인", "detail": "SYNTHETIC evidence", "link": ""},
     {"code": "MISSING_SIGNATURE", "message": "서명 없음 (확인필요)",
      "how_to_fix": "서명 없음 확인", "detail": "SYNTHETIC evidence", "link": "", "title": "서명 없음"}),
    ({"code": "SYNTHETIC_UNKNOWN", "message": "합성 과거 사유입니다. 다음 문장입니다."},
     {"code": "SYNTHETIC_UNKNOWN", "message": "합성 과거 사유입니다. 다음 문장입니다.", "title": "합성 과거 사유입니다"}),
    ({"message": ""}, {"message": "", "title": "규칙 엔진 확인 사유"}),
    ({"code": "MISSING_SIGNATURE", "message": None},
     {"code": "MISSING_SIGNATURE", "message": None, "title": "서명 없음"}),
])
def test_literal_reason_projection_preserves_source(source, expected):
    before = deepcopy(source)
    assert readable_reason(source) == expected
    assert source == before


@pytest.mark.parametrize("title", ["합성 입력 제목", "", None, 123, {"unexpected": True}, ["합성"]])
def test_incoming_title_is_not_an_application_field(client, title):
    response = client.post("/api/applications", json={"program_code": "double_savings", "title": title})
    assert response.status_code == 200
    aid = response.json()["id"]
    assert "title" not in response.json()
    assert client.patch(f"/api/applications/{aid}", json={"title": title, "form1": {"address": "합성 주소"}}).status_code == 200
    response = client.get(f"/api/applications/{aid}")
    assert response.status_code == 200 and "title" not in response.json()
    with models.get_session() as session:
        stored = session.get(models.Application, aid)
        assert "title" not in stored.model_dump()
        assert "title" not in stored.form1_json
        assert stored.form1_json["address"] == "합성 주소"


def test_legacy_findings_decorated_only_for_officer_and_never_persisted(client, monkeypatch):
    monkeypatch.setenv("OFFICER_PASSWORD", "SYNTHETIC contract password")
    monkeypatch.setenv("OFFICER_SESSION_SECRET", "SYNTHETIC contract secret")
    application = ready(make_application(premium=1))
    claim_synthetic_application(client, application.id)
    findings = [{"code": "LOW_IMAGE_QUALITY", "severity": "NEEDS_REVIEW", "message": "합성 내부 사유"}]
    with models.get_session() as session:
        document = session.exec(select(models.Document).where(models.Document.application_id == application.id,
                                models.Document.slot_key == "resident_abstract")).one()
        document.findings_json = deepcopy(findings)
        session.add(document)
        session.commit()
        did = document.id
        before = document_dict(document)
        assert before["findings"] == []
    assert client.get(f"/api/applications/{application.id}/final-check").json()["can_submit"]
    assert client.post(f"/api/applications/{application.id}/submit").status_code == 200
    assert client.get(f"/api/officer/applications/{application.id}").status_code == 401
    authenticate_officer(client, monkeypatch)
    with models.get_session() as session:
        review_before = deepcopy(session.exec(select(models.Review).where(models.Review.application_id == application.id)).one().model_dump())
    for _ in range(2):
        response = client.get(f"/api/officer/applications/{application.id}")
        assert response.status_code == 200
        detail = response.json()
        found = next(d for d in detail["documents"] if d["document_id"] == did)
        assert found["findings"] == [{**findings[0], "title": "화질이 낮음"}]
        assert all(isinstance(r["title"], str) and r["title"] for r in detail["ai"]["reasons"])
    with models.get_session() as session:
        document = session.get(models.Document, did)
        assert document.findings_json == findings
        assert document_dict(document) == before
        review_after = session.exec(select(models.Review).where(models.Review.application_id == application.id)).one().model_dump()
        assert review_after == review_before


@pytest.mark.parametrize("title", ["SYNTHETIC private title", "", None, 123, {}])
def test_stored_title_never_leaks_through_applicant_allowlist(title):
    document = models.Document(application_id=1, slot_key="resident_abstract", file_path="FAKE.pdf",
                               file_format="pdf", stage1_status="FAIL", findings_json=[{
                                   "code": "LOW_IMAGE_QUALITY", "severity": "FAIL", "message": "합성 공개 사유",
                                   "title": title, "detail": "SYNTHETIC private detail"}])
    assert document_dict(document)["findings"] == [{"code": "LOW_IMAGE_QUALITY", "severity": "FAIL", "message": "합성 공개 사유"}]
