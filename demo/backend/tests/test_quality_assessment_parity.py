"""Synthetic uploads share quality grades with submission-time rechecking."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from PIL import Image
import pytest

from demo.backend import models, upload_assessment
from demo.backend.api import documents, officer
from demo.backend.api.common import document_fact
from demo.backend.api.review import _run_review
from demo.backend.engine_adapter import apply_runtime_overrides, run_pipeline, to_engine_applicant, to_engine_documents
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_check import (
    CheckFinding, CheckResult, QUALITY_REVIEW_GUIDANCE, check_document, finalize_image_quality,
)
from demo.backend.rules.doc_types import DocType
from demo.backend.rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE, PROGRAMS
from demo.backend.rules.required_docs import ApplicantDocInput, DocRequirement, build_checklist
from demo.backend.rules.subsidy import Selection, SubsidyType
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_portal_uploads import client
from demo.backend.tools.verify_upload import _row
from engine.models import Status
from engine.stage1_document_check import IMAGE_QUALITY_REVIEW_MESSAGE, image_quality_status


ISSUED = date(2026, 4, 7)


def pipeline_for(req, read, result, *, program_code=DOUBLE_SAVINGS):
    row = _row(req, Path("FAKE-quality.png"), read, result)
    converted = to_engine_documents([document_fact(row)])
    applicant = to_engine_applicant(
        application_no="FAKE-QUALITY", name="가상신청", birth_date=date(1999, 1, 1),
        residence_region="전주시", program=PROGRAMS[program_code], income_percent=90,
    )
    return run_pipeline(applicant, converted, [req]), converted[0]


def exam_requirements(count):
    apply_runtime_overrides()
    checklist = build_checklist(PROGRAMS[JOB_PACKAGE], ApplicantDocInput(
        subsidy_selections=[Selection(SubsidyType.CERTIFICATE, count)],
    ))
    return [req for req in checklist if req.slot_key.endswith("_exam")]


def exam_read(kind, quality):
    return OcrResult(kind, .95, image_quality=quality, issue_date=ISSUED, tier="localocr", fields={
        "성명": "가상신청", "생년월일": "1999-01-01", "발급일": ISSUED.isoformat(), "응시일": ISSUED.isoformat(),
    })


def test_real_checklist_accepted_exam_alternate_keeps_quality_review_in_submission():
    req = exam_requirements(1)[0]
    assert req.doc_type == DocType.EXAM_CONFIRMATION
    assert DocType.EXAM_TRANSCRIPT in req.accepted_doc_types
    read = exam_read(DocType.EXAM_TRANSCRIPT, .55)
    result = check_document(req, read)
    pipeline, converted = pipeline_for(req, read, result, program_code=JOB_PACKAGE)
    assert result.status == pipeline.stage1.status.value == "NEEDS_REVIEW"
    assert converted.doc_type == str(DocType.EXAM_TRANSCRIPT)
    assert "WRONG_DOCUMENT_TYPE" not in {f.code.value for f in pipeline.stage1.findings}
    assert any(f.code.value == "LOW_IMAGE_QUALITY" for f in pipeline.stage1.findings)


@pytest.mark.parametrize("kinds", [
    (DocType.EXAM_TRANSCRIPT, DocType.EXAM_CONFIRMATION),
    (DocType.EXAM_CONFIRMATION, DocType.EXAM_CONFIRMATION),
    (DocType.EXAM_TRANSCRIPT, DocType.EXAM_TRANSCRIPT),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("content_failure", [False, True])
def test_quality_review_and_content_failure_survive_other_exam_documents(kinds, reverse, content_failure):
    requirements = exam_requirements(2)
    facts = []
    for index, (req, kind) in enumerate(zip(requirements, kinds)):
        read = exam_read(kind, .55 if index == 0 else .9)
        if index == 0 and content_failure:
            read.fields.pop("응시일")
            read.tier = "pdftext"
        result = check_document(req, read)
        facts.append(document_fact(_row(req, Path("FAKE-exam.png"), read, result)))
    assert facts[0]["status"] == ("FAIL" if content_failure else "NEEDS_REVIEW")
    assert facts[1]["status"] == "PASS"
    if reverse:
        facts.reverse()
    converted = to_engine_documents(facts)
    original_types = [doc.doc_type for doc in converted]
    applicant = to_engine_applicant(
        application_no="FAKE-EXAMS", name="가상신청", birth_date=date(1999, 1, 1),
        residence_region="전주시", program=PROGRAMS[JOB_PACKAGE], income_percent=None,
    )
    pipeline = run_pipeline(applicant, converted, requirements)
    assert pipeline.stage1.status.value == ("FAIL" if content_failure else "NEEDS_REVIEW")
    assert [doc.doc_type for doc in converted] == original_types
    quality = [f for f in pipeline.stage1.findings if f.code.value == "LOW_IMAGE_QUALITY"]
    assert quality and all(f.message == IMAGE_QUALITY_REVIEW_MESSAGE for f in quality)


@pytest.mark.parametrize("evidence", ["absent", "legacy-failure", "good-quality"])
def test_accepted_exam_matching_without_quality_review_keeps_existing_behavior(evidence):
    req = exam_requirements(1)[0]
    read = exam_read(DocType.EXAM_TRANSCRIPT, .9 if evidence == "good-quality" else .55)
    result = check_document(req, read)
    fact = document_fact(_row(req, Path("FAKE-exam.png"), read, result))
    if evidence == "absent":
        fact.pop("findings")
    elif evidence == "legacy-failure":
        fact["findings"][0]["severity"] = "FAIL"
        fact["status"] = "FAIL"
    applicant = to_engine_applicant(
        application_no="FAKE-EXAM", name="가상신청", birth_date=date(1999, 1, 1),
        residence_region="전주시", program=PROGRAMS[JOB_PACKAGE], income_percent=None,
    )
    pipeline = run_pipeline(applicant, to_engine_documents([fact]), [req])
    assert pipeline.stage1.status == Status.FAIL
    assert "WRONG_DOCUMENT_TYPE" in {f.code.value for f in pipeline.stage1.findings}


@pytest.mark.parametrize("variant", ["unknown", "unreadable"])
@pytest.mark.parametrize("reverse", [False, True])
def test_quality_failure_cannot_be_shadowed_by_another_readable_exam(variant, reverse):
    requirements = exam_requirements(2)
    reads = [exam_read(None if variant == "unknown" else DocType.EXAM_CONFIRMATION, .55),
             exam_read(DocType.EXAM_CONFIRMATION, .9)]
    if variant == "unreadable":
        reads[0].fields.pop("응시일")
    facts = []
    for req, read in zip(requirements, reads):
        result = check_document(req, read)
        facts.append(document_fact(_row(req, Path("FAKE-exam.png"), read, result)))
    assert facts[0]["status"] == "FAIL" and facts[1]["status"] == "PASS"
    if reverse:
        facts.reverse()
    applicant = to_engine_applicant(
        application_no="FAKE-EXAMS", name="가상신청", birth_date=date(1999, 1, 1),
        residence_region="전주시", program=PROGRAMS[JOB_PACKAGE], income_percent=None,
    )
    pipeline = run_pipeline(applicant, to_engine_documents(facts), requirements)
    assert pipeline.stage1.status == Status.FAIL
    quality = [f for f in pipeline.stage1.findings if f.code.value == "LOW_IMAGE_QUALITY"]
    assert quality and all(f.message != IMAGE_QUALITY_REVIEW_MESSAGE for f in quality)


@pytest.mark.parametrize("quality", [.59, .6, .9])
@pytest.mark.parametrize("variant", ["complete", "unreadable", "unknown"])
def test_upload_and_submission_share_quality_boundary_and_required_readability(quality, variant):
    req = DocRequirement("work_proof", DocType.FARM_BIZ_CERT, "합성 서류", required_fields=["성명"])
    read = OcrResult(
        None if variant == "unknown" else DocType.FARM_BIZ_CERT, .95,
        image_quality=quality, issue_date=ISSUED, tier="localocr",
        fields={} if variant == "unreadable" else {"성명": "가상신청"},
    )
    result = check_document(req, read, file_format="png")
    pipeline, converted = pipeline_for(req, read, result)
    expected = "FAIL" if quality < .6 and variant != "complete" else (
        "PASS" if quality >= .6 and variant == "complete" else "NEEDS_REVIEW"
    )
    assert result.status == pipeline.stage1.status.value == pipeline.status.value == expected
    assert converted.image_quality_score == quality
    quality_findings = [f for f in result.findings if f.code == "LOW_IMAGE_QUALITY"]
    engine_findings = [f for f in pipeline.stage1.findings if f.code.value == "LOW_IMAGE_QUALITY"]
    assert len(quality_findings) == len(engine_findings) == int(quality < .6)
    if variant == "complete" and quality < .6:
        assert quality_findings[0].severity == "NEEDS_REVIEW"
        assert quality_findings[0].message == engine_findings[0].message == IMAGE_QUALITY_REVIEW_MESSAGE
        assert quality_findings[0].how_to_fix == QUALITY_REVIEW_GUIDANCE
    if quality < .6 and variant != "complete":
        assert quality_findings[0].severity == "FAIL"


def test_quality_review_preserves_independent_required_content_failure_in_submission():
    req = DocRequirement("work_proof", DocType.FARM_BIZ_CERT, "합성 서류", required_fields=["성명"])
    read = OcrResult(DocType.FARM_BIZ_CERT, .95, image_quality=.55,
                     issue_date=ISSUED, fields={"발급일": ISSUED.isoformat()}, tier="pdftext")
    result = check_document(req, read)
    assert result.status == "FAIL"
    assert [(f.code, f.severity) for f in result.findings] == [
        ("MISSING_REQUIRED_FIELD", "FAIL"), ("LOW_IMAGE_QUALITY", "NEEDS_REVIEW"),
    ]
    pipeline, converted = pipeline_for(req, read, result)
    assert converted.has_confirmed_document_failure is True
    assert pipeline.stage1.status == pipeline.status == Status.FAIL


@pytest.mark.parametrize("evidence", [None, [], [{"code": "LOW_IMAGE_QUALITY"}],
                                         [{"code": "LOW_IMAGE_QUALITY", "severity": "FAIL"}]])
def test_legacy_quality_evidence_keeps_conservative_failure(evidence):
    row = {
        "doc_type": str(DocType.FARM_BIZ_CERT), "confidence": .95,
        "image_quality": .55, "issue_date": ISSUED,
    }
    if evidence is not None:
        row["findings"] = evidence
    converted = to_engine_documents([row])[0]
    assert image_quality_status(
        converted.image_quality_score,
        classification_succeeded=converted.classification_succeeded,
        required_fields_readable=converted.required_fields_readable,
    ) == Status.FAIL
    assert image_quality_status(.6) == Status.PASS


def test_saved_quality_review_cannot_override_failed_classification_or_good_quality_scope():
    row = {
        "expected_doc_type": str(DocType.FARM_BIZ_CERT), "confidence": .95,
        "image_quality": .55, "status": "NEEDS_REVIEW",
        "findings": [{"code": "LOW_IMAGE_QUALITY", "severity": "NEEDS_REVIEW"}],
    }
    converted = to_engine_documents([row])[0]
    assert image_quality_status(
        converted.image_quality_score,
        classification_succeeded=converted.classification_succeeded,
        required_fields_readable=converted.required_fields_readable,
    ) == Status.FAIL
    row.update(doc_type=str(DocType.FARM_BIZ_CERT), image_quality=.9, status="FAIL")
    assert to_engine_documents([row])[0].has_confirmed_document_failure is False


@pytest.mark.parametrize("missing", ["none", "mark", "signature"])
def test_late_consent_observations_finalize_quality_before_submission(tmp_path, monkeypatch, missing):
    req = DocRequirement("admin_info_consent", DocType.ADMIN_INFO_CONSENT, "합성 동의서")
    read = OcrResult(DocType.ADMIN_INFO_CONSENT, .95, image_quality=.55,
                     fields={"성명": "가상신청", "생년월일": "1999-01-01"})
    monkeypatch.setattr("demo.backend.ocr.admin_consent_scan.inspect_admin_consent_scan", lambda _: {
        "동의여부": "확인필요" if missing == "mark" else "동의함",
        "서명잉크확인": "확인필요" if missing == "signature" else "있음",
    })
    _, result = upload_assessment.assess_upload(
        tmp_path / "FAKE-consent.png", req, paper_admin_consent=True, reader=lambda *_: read,
    )
    expected = "NEEDS_REVIEW" if missing == "none" else "FAIL"
    assert result.status == expected
    assert next(f.severity for f in result.findings if f.code == "LOW_IMAGE_QUALITY") == expected
    pipeline, _ = pipeline_for(req, read, result)
    assert pipeline.stage1.status.value == expected


def test_late_receipt_ocr_unavailability_changes_quality_review_to_failure(tmp_path):
    req = DocRequirement("exam_receipt", DocType.PAYMENT_RECEIPT, "합성 영수증")
    read = OcrResult(DocType.PAYMENT_RECEIPT, .95, image_quality=.55,
                     issue_date=ISSUED, fields={"결제금액": "1000"}, tier="none")
    assert check_document(req, read).status == "NEEDS_REVIEW"
    _, result = upload_assessment.assess_upload(tmp_path / "FAKE-receipt.png", req, reader=lambda *_: read)
    assert result.status == "FAIL"
    assert "RECEIPT_OCR_UNAVAILABLE" in result.codes
    assert next(f.severity for f in result.findings if f.code == "LOW_IMAGE_QUALITY") == "FAIL"
    pipeline, _ = pipeline_for(req, read, result)
    assert pipeline.stage1.status == Status.FAIL


def test_quality_finalization_retains_one_warning_and_independent_reading_evidence():
    req = DocRequirement("nhis_payment", DocType.NHIS_PAYMENT, "합성 납부확인서")
    read = OcrResult(DocType.NHIS_PAYMENT, .4, image_quality=.55, fields={"성명": "가상신청"})
    result = CheckResult("NEEDS_REVIEW", [CheckFinding("MISSING_BILLING_MONTHS", "합성 미판독", severity="NEEDS_REVIEW")])
    for _ in range(2):
        finalize_image_quality(req, read, result)
    assert result.status == "FAIL"
    assert result.codes.count("LOW_IMAGE_QUALITY") == 1
    assert "MISSING_BILLING_MONTHS" in result.codes


@pytest.mark.parametrize("variant", ["complete", "unreadable", "unknown", "content-failure"])
def test_actual_upload_final_check_submission_and_officer_quality_agree(client, tmp_path, monkeypatch, variant):
    app = ready(make_application(premium=0))
    fields = {
        "성명": "가상신청", "생년월일": "1999-01-01", "발급일": ISSUED.isoformat(),
        "초본신청인성명": "가상신청", "초본신청인생년월일": "1999-01-01", "전입일": "2020-01-01",
    }
    if variant == "unreadable":
        fields.pop("초본신청인성명")
    if variant == "content-failure":
        fields["주소날짜검증자료"] = json.dumps({"status": "MISSING", "confidence": .95})
    read = OcrResult(
        None if variant == "unknown" else DocType.RESIDENT_ABSTRACT, .95,
        image_quality=.55, issue_date=ISSUED, fields=fields, tier="localocr", classification_confidence=.95,
    )
    monkeypatch.setattr(documents, "read_document", lambda *_: deepcopy(read))
    path = tmp_path / "FAKE-quality.png"
    Image.new("RGB", (970, 1282), "white").save(path)
    response = client.post(
        f"/api/applications/{app.id}/documents",
        files={"file": (path.name, path.read_bytes(), "image/png")},
        data={"slot_key": "resident_abstract", "declared_issue_date": ISSUED.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    expected = "NEEDS_REVIEW" if variant == "complete" else "FAIL"
    assert body["status"] == expected
    listed = client.get(f"/api/applications/{app.id}/documents").json()
    assert next(row for row in listed if row["document_id"] == body["document_id"])["status"] == expected
    final = client.get(f"/api/applications/{app.id}/final-check").json()
    document_blockers = [row for row in final["blockers"] if row["kind"] == "document" and row["target"] == "resident_abstract"]
    assert bool(document_blockers) is (expected == "FAIL")
    with models.get_session() as session:
        stored = session.get(models.Document, body["document_id"])
        quality = next(f for f in stored.findings_json if f["code"] == "LOW_IMAGE_QUALITY")
        assert quality["severity"] == ("NEEDS_REVIEW" if variant in {"complete", "content-failure"} else "FAIL")
        assert officer._document_view(stored, {})["findings"] == stored.findings_json
    rerun = _run_review(app)
    assert rerun.stage1_status == rerun.final_status == expected
    submitted = client.post(f"/api/applications/{app.id}/submit")
    assert submitted.status_code == (200 if expected == "NEEDS_REVIEW" else 400)
    if expected == "NEEDS_REVIEW":
        detail = client.get(f"/api/officer/applications/{app.id}").json()
        assert detail["ai"]["stage1_status"] == detail["ai"]["final_status"] == "NEEDS_REVIEW"
        doc = next(row for row in detail["documents"] if row["document_id"] == body["document_id"])
        assert doc["status"] == "NEEDS_REVIEW"
        assert next(f for f in doc["findings"] if f["code"] == "LOW_IMAGE_QUALITY")["how_to_fix"] == QUALITY_REVIEW_GUIDANCE
