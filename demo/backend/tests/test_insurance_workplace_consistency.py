"""Synthetic end-to-end name review, independent failures and local evidence."""
from datetime import date
import json

import pytest

from demo.backend.ocr.localocr import _from_insurance4
from demo.backend.rules.doc_check import check_document
from demo.backend.rules.identity import Identity
from demo.backend.tests.test_insurance_portal import req
from engine_v2.extractors import insurance_workplace as contract
from engine_v2.tests.nhis_form_samples import NAME as PERSON, text_pdf
from engine_v2.tests.test_insurance_workplace_consistency import (
    NAME, OTHER, synthetic_pages, synthetic_cells, extract,
)


def converted(form="government24", conflict=True):
    pages = synthetic_pages(form, [NAME, OTHER if conflict else NAME, NAME, NAME])
    return _from_insurance4(extract(pages), pages)


@pytest.mark.parametrize("form", ["government24", "portal"])
def test_B_name_only_review_is_typed_without_generic_confidence_damage(form):
    normal, uncertain = converted(form, False), converted(form)
    result = check_document(req(), uncertain, identity=Identity(PERSON, date(1990, 1, 1)))
    assert result.status == "NEEDS_REVIEW"
    assert result.codes == [contract.CODE]
    assert uncertain.confidence == normal.confidence >= .85
    for key in ("성명", "생년월일", "발급일", "근로근거신뢰도", "판독검증", "보험별가입여부",
                "근로관련최초취득일", "근로관련최근취득일"):
        assert uncertain.fields[key] == normal.fields[key]
    assert contract.name_review(uncertain.fields)
    assert uncertain.bboxes["국민연금 사업장명칭"].x0 > uncertain.bboxes["가입내역"].x0
    assert uncertain.bboxes[contract.STATE_FIELD].x0 == uncertain.bboxes["국민연금 사업장명칭"].x0
    assert result.findings[0].detail == contract.REASON
    assert all(secret not in result.findings[0].detail for secret in [NAME, OTHER, "12345678901"])


@pytest.mark.parametrize("form", ["government24", "portal"])
@pytest.mark.parametrize("defect,expected", [("identity", "IDENTITY_MISMATCH"),
    ("declared", "DECLARED_DATE_MISMATCH")])
def test_K_independent_confirmed_failure_stays_fail(form, defect, expected):
    ocr = converted(form)
    identity = Identity("가상다른인" if defect == "identity" else PERSON, date(1990, 1, 1))
    result = check_document(req(), ocr, date(2026, 3, 4) if defect == "declared" else None,
                            identity=identity)
    assert result.status == "FAIL"
    assert contract.CODE in result.codes
    assert any(f.code == expected and f.severity == "FAIL" for f in result.findings)


@pytest.mark.parametrize("defect", ["no-state", "no-reason", "unknown-reason", "no-proof", "bad-proof",
    "stale-rows", "stale-list", "no-groups", "bool-index", "duplicate-index", "inactive", "same-names"])
def test_E_stale_or_malformed_state_does_not_establish_scoped_review(defect):
    ocr = converted()
    fields = ocr.fields
    if defect == "no-state": fields.pop(contract.STATE_FIELD)
    elif defect == "no-reason": fields.pop(contract.REASON_FIELD)
    elif defect == "unknown-reason": fields[contract.REASON_FIELD] = "FAKE_UNKNOWN"
    elif defect == "no-proof": fields.pop(contract.PROOF_FIELD)
    elif defect == "bad-proof": fields[contract.PROOF_FIELD] = "null"
    elif defect == "stale-rows": fields["가입내역"] += " "
    elif defect == "stale-list": fields["사업장명칭목록"] = json.dumps([NAME])
    else:
        proof = json.loads(fields[contract.PROOF_FIELD])
        if defect == "no-groups": proof["groups"] = []
        elif defect == "bool-index": proof["groups"] = [[False, 1]]
        elif defect == "duplicate-index": proof["groups"] = [[0, 0, 1]]
        else:
            rows = json.loads(fields["가입내역"])
            if defect == "inactive": rows[1]["상태"] = "미가입"
            else:
                for row in rows: row["사업장명칭"] = NAME
            fields["가입내역"] = json.dumps(rows, ensure_ascii=False)
            proof = json.loads(contract.proof(fields["가입내역"], [[0, 1]]))
        fields[contract.PROOF_FIELD] = json.dumps(proof)
    assert not contract.name_review(fields)
    assert contract.CODE not in check_document(req(), ocr).codes


@pytest.mark.parametrize("form", ["government24", "portal"])
def test_L_actual_synthetic_text_pdf_routing_delivers_scoped_review(tmp_path, monkeypatch, form):
    from demo.backend.ocr import read_document
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    path = text_pdf(tmp_path / "FAKE-insurance.pdf", synthetic_cells(form, [NAME, OTHER, NAME, NAME]))
    ocr = read_document(str(path))
    result = check_document(req(), ocr, identity=Identity(PERSON, date(1990, 1, 1)))
    assert ocr.engine == "pdftext"
    assert result.status == "NEEDS_REVIEW"
    assert result.codes == [contract.CODE]
    assert contract.name_review(ocr.fields)


def test_N_safe_diagnostics_allow_fixed_code_only():
    from demo.backend.tools.verify_upload import SAFE_CODES
    assert contract.CODE in SAFE_CODES


def test_K_low_quality_review_is_preserved_alongside_name_review():
    ocr = converted()
    ocr.image_quality = .1
    result = check_document(req(), ocr)
    assert result.status == "NEEDS_REVIEW"
    assert {contract.CODE, "LOW_IMAGE_QUALITY"} <= set(result.codes)
    assert all(f.severity == "NEEDS_REVIEW" for f in result.findings)
