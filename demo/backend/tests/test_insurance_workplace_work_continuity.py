"""Name-only review preserves independent work evidence through stored facts."""
from datetime import date
import json

import pytest
from sqlmodel import select

from demo.backend import models
from demo.backend.api.common import document_fact
from demo.backend.api.officer import Entry, _eligibility
from demo.backend.api.review import _run_review
from demo.backend.rules.doc_check import CheckFinding, check_document
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.identity import Identity
from demo.backend.rules.programs import PROGRAMS, DOUBLE_SAVINGS
from demo.backend.rules.required_docs import WorkCategory
from demo.backend.rules.work_continuity import assess_work
from demo.backend.tests.test_income_review import isolated_db, make_application
from demo.backend.tests.test_insurance_portal import req
from demo.backend.tests.test_insurance_workplace_consistency import converted
from engine_v2.extractors import insurance_workplace as contract
from engine_v2.tests.nhis_form_samples import NAME as PERSON


IDENTITY = {"name": PERSON, "birth": "1990-01-01"}


def refresh_proof(fields):
    fields[contract.PROOF_FIELD] = contract.proof(fields["가입내역"], [[0, 1, 2, 3]])


def fact(acquired="2020-01-01", form="government24"):
    ocr = converted(form)
    rows = json.loads(ocr.fields["가입내역"])
    for row in rows:
        row["자격취득일"] = acquired
    ocr.fields["가입내역"] = json.dumps(rows, ensure_ascii=False)
    refresh_proof(ocr.fields)
    result = check_document(req(), ocr, identity=Identity(PERSON, date(1990, 1, 1)))
    stored = models.Document(application_id=1, slot_key="work_proof", doc_type=str(DocType.INSURANCE_4),
        expected_doc_type=str(DocType.INSURANCE_4), file_path="FAKE-insurance.pdf", file_format="pdf",
        stage1_status=result.status, findings_json=[f.as_dict() for f in result.findings],
        ocr_json={"confidence": ocr.confidence, "image_quality": ocr.image_quality,
                  "issue_date": ocr.issue_date.isoformat(), "fields": ocr.fields})
    return document_fact(stored)


def assess(doc):
    return assess_work(PROGRAMS[DOUBLE_SAVINGS], date(2026, 3, 3), WorkCategory.EMPLOYEE,
                       [doc], IDENTITY)


@pytest.mark.parametrize("form", ["government24", "portal"])
@pytest.mark.parametrize("acquired,expected", [("2020-01-01", "MET"), ("2026-01-01", "NOT_MET")])
def test_K_stored_name_only_review_keeps_independent_work_result(form, acquired, expected):
    doc = fact(acquired, form)
    assert doc["status"] == "NEEDS_REVIEW"
    assert [f["code"] for f in doc["findings"]] == [contract.CODE]
    assert assess(doc).status == expected
    assert doc["status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize("defect", ["empty", "missing", "none", "mapping", "malformed", "missing-key",
    "wrong-severity", "unknown-code", "mixed-review", "mixed-fail", "stale", "wrong-state", "wrong-type", "fail-status"])
def test_K_no_generic_review_exception_or_stale_state(defect):
    doc = fact()
    if defect == "empty": doc["findings"] = []
    elif defect == "missing": doc.pop("findings")
    elif defect == "none": doc["findings"] = None
    elif defect == "mapping": doc["findings"] = {"code": contract.CODE}
    elif defect == "malformed": doc["findings"] = ["FAKE"]
    elif defect == "missing-key": doc["findings"][0].pop("message")
    elif defect == "wrong-severity": doc["findings"][0]["severity"] = "FAIL"
    elif defect == "unknown-code": doc["findings"][0]["code"] = "FAKE_UNKNOWN"
    elif defect.startswith("mixed"):
        doc["findings"].append(CheckFinding("LOW_OCR_CONFIDENCE", "가상", severity=
                                          "FAIL" if defect == "mixed-fail" else "NEEDS_REVIEW").as_dict())
    elif defect == "stale": doc["fields"]["가입내역"] += " "
    elif defect == "wrong-state": doc["fields"][contract.STATE_FIELD] = "확실"
    elif defect == "wrong-type": doc["doc_type"] = str(DocType.NHIS_ACQUISITION_LOSS)
    else: doc["status"] = "FAIL"
    assert assess(doc).status == "UNDETERMINED"


@pytest.mark.parametrize("defect", ["identity", "birth", "confidence", "source", "quality", "validation",
    "structure", "issue", "missing-date", "conflicting-date", "row-identity", "date-confidence"])
def test_K_all_independent_guards_survive_name_only_allowance(defect):
    doc = fact()
    fields = doc["fields"]
    if defect == "identity": fields["성명"] = "가상다른인"
    elif defect == "birth": fields["생년월일"] = "1991-01-01"
    elif defect == "confidence": doc["confidence"] = .4
    elif defect == "source": fields["근로근거신뢰도"] = ".4"
    elif defect == "quality": doc["image_quality"] = .4
    elif defect == "validation": fields["판독검증실패"] = "date_formats"
    elif defect == "structure": fields["판독검증"] = "1/2 통과"
    elif defect == "issue":
        doc["issue_date"] = date(2026, 3, 2)
        fields["발급일"] = "2026-03-02"
    else:
        rows = json.loads(fields["가입내역"])
        if defect == "missing-date": rows[1]["자격취득일"] = ""
        elif defect == "conflicting-date": rows[1]["자격취득일"] = "2026-04-01"
        elif defect == "row-identity": rows[1]["성명"] = "가상다른인"
        else: rows[1]["자격취득일신뢰도"] = .4
        fields["가입내역"] = json.dumps(rows, ensure_ascii=False)
        refresh_proof(fields)
    assert assess(doc).status == "UNDETERMINED"


@pytest.mark.parametrize("acquired,expected", [("2020-01-01", "MET"), ("2026-01-01", "NOT_MET")])
def test_K_review_writer_officer_and_eligibility_preserve_both_conclusions(isolated_db, acquired, expected):
    app = make_application(premium=0)
    with models.get_session() as session:
        doc = session.exec(select(models.Document).where(models.Document.application_id == app.id,
                            models.Document.doc_type == str(DocType.INSURANCE_4))).one()
        data = {**doc.ocr_json, "fields": dict(doc.ocr_json["fields"])}
        fields = data["fields"]
        rows = json.loads(fields["가입내역"])
        for i, row in enumerate(rows):
            row.update({"사업장관리번호": "12345678901", "사업장명칭": "가상솔빗" if i == 1 else "가상솔빛",
                        "자격취득일": acquired, "자격취득일신뢰도": .99})
        fields["가입내역"] = json.dumps(rows, ensure_ascii=False)
        fields.update({contract.STATE_FIELD: "불확실", contract.REASON_FIELD: contract.REASON,
                       contract.COUNT_FIELD: "미확정", "사업장명칭목록": json.dumps(["가상솔빛", "가상솔빗"])})
        refresh_proof(fields)
        doc.ocr_json = data
        doc.stage1_status = "NEEDS_REVIEW"
        doc.findings_json = [CheckFinding(contract.CODE, "가상 명칭 확인", severity="NEEDS_REVIEW").as_dict()]
        session.add(doc); session.commit()
    review = _run_review(app)
    work = review.review_payload_json["work_continuity"]
    assert work["status"] == expected
    assert review.final_status == ("FAIL" if expected == "NOT_MET" else "NEEDS_REVIEW")
    check = next(item for item in _eligibility(Entry(app, review), {}) if item["key"] == "work")
    assert check["ok"] is (expected == "MET")
    assert next(item for item in review.score_json["items"] if item["key"] == "work")["score"] > 0
