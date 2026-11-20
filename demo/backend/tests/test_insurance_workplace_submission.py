"""Actual applicant final-check/submit keeps name review and independent internal failures."""
import json

import pytest
from sqlmodel import select

from demo.backend import models
from demo.backend.api.common import document_dict
from demo.backend.api.review import _run_review
from demo.backend.rules.doc_check import CheckFinding
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tests.security_support import claim_synthetic_application
from engine_v2.extractors import insurance_workplace as contract


@pytest.mark.parametrize("acquired,work_met", [("2020-01-01", True), ("2026-01-01", False)])
def test_K_name_review_submission_keeps_independent_internal_work_failure(client, acquired, work_met):
    app = ready(make_application(premium=1))
    with models.get_session() as session:
        doc = session.exec(select(models.Document).where(models.Document.application_id == app.id,
                            models.Document.doc_type == str(DocType.INSURANCE_4))).one()
        data = {**doc.ocr_json, "fields": dict(doc.ocr_json["fields"])}
        fields = data["fields"]; rows = json.loads(fields["가입내역"])
        for i, row in enumerate(rows):
            row.update({"사업장관리번호": "12345678901", "사업장명칭": "가상솔빗" if i == 1 else "가상솔빛",
                        "자격취득일": acquired, "자격취득일신뢰도": .99})
        fields["가입내역"] = json.dumps(rows, ensure_ascii=False)
        fields.update({contract.STATE_FIELD: "불확실", contract.REASON_FIELD: contract.REASON,
            contract.COUNT_FIELD: "미확정", "사업장명칭목록": json.dumps(["가상솔빛", "가상솔빗"])})
        fields[contract.PROOF_FIELD] = contract.proof(fields["가입내역"], [[0, 1, 2, 3]])
        doc.ocr_json = data; doc.stage1_status = "NEEDS_REVIEW"
        doc.findings_json = [CheckFinding(contract.CODE, "가상 명칭 확인", severity="NEEDS_REVIEW").as_dict()]
        assert document_dict(doc)["status"] == "UPLOADED"
        assert document_dict(doc)["findings"] == []
        session.add(doc); session.commit(); document_id = doc.id
    claim_synthetic_application(client, app.id)
    review = _run_review(app)
    assert review.review_payload_json["work_continuity"]["status"] == ("MET" if work_met else "NOT_MET")
    prepared = client.get(f"/api/applications/{app.id}/final-check").json()
    assert prepared["can_submit"] is True
    assert "WORK_CONTINUITY_NOT_MET" not in {b["code"] for b in prepared["blockers"]}
    response = client.post(f"/api/applications/{app.id}/submit")
    assert response.status_code == 200
    with models.get_session() as session:
        stored = session.get(models.Document, document_id)
        assert stored.stage1_status == "NEEDS_REVIEW"
        assert [f["code"] for f in stored.findings_json] == [contract.CODE]

        reviewed = session.exec(select(models.Review).where(models.Review.application_id == app.id)).one()
        assert reviewed.review_payload_json["work_continuity"]["status"] == ("MET" if work_met else "NOT_MET")
        assert reviewed.final_status == ("NEEDS_REVIEW" if work_met else "FAIL")
