"""Authored payment words/PDFs verify routes, review and financial isolation."""
from copy import deepcopy
import json

import pytest

from demo.backend.ocr import read_document
from demo.backend.ocr.localocr import LocalOcr, _from_nhis
from demo.backend.rules.doc_check import _check_billing_months
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_payment_failure_certainty import requirement
from demo.backend.tests.test_p2_nhis_uploads import image_pdf, use_own_words
from demo.backend.tests.test_portal_uploads import client, new_app, upload
from engine_v2.extractors import nhis_payment, payment_period
from engine_v2.schemas.models import DocType as V2DocType
from engine_v2.tests import p2_payment_samples as base, payment_stage2_samples as shapes
from engine_v2.tests.test_income_payment_evidence import _text_pdf
from engine_v2.tools import batch_assess as batch


def test_normal_text_upload_uses_text_words_without_calling_own(tmp_path, monkeypatch):
    import demo.backend.ocr as chain
    from engine_v2.pipeline import ocr
    cells, size = base.payment()
    path = _text_pdf(tmp_path / "FAKE-stage2-text.pdf", cells, size)
    monkeypatch.setenv("ENGINE_V2_OCR", "own")
    monkeypatch.setattr(chain, "CHAIN", [LocalOcr()])
    monkeypatch.setitem(ocr.ENGINES, "own", lambda *_: pytest.fail("text page invoked own"))
    result = read_document(str(path), DocType.NHIS_PAYMENT)
    assert result.engine == "pdftext"
    assert json.loads(result.fields[payment_period.FIELD])["status"] == "READABLE"
    assert _check_billing_months(result, requirement()) == []


def test_batch_forces_own_for_text_pdf_and_does_not_merge_reference(tmp_path, monkeypatch):
    cells, size = base.payment()
    path = _text_pdf(tmp_path / "FAKE-stage2-batch.pdf", cells, size)
    _, references, coverage = batch._inspect(path)
    assert coverage == 1
    calls = []

    def own_words(engine, page):
        calls.append(engine)
        result = deepcopy(references[page.page])
        result.engine = engine
        # A positive outside the independently printed range must conflict.
        next(w for w in result.words if w.text == "0").text = "7"
        return result

    monkeypatch.setattr(batch, "_recognize", own_words)
    observed = []
    original = batch._assess

    def assess(source, kind, result):
        observed.append(json.loads(result.fields[payment_period.FIELD])["status"])
        return original(source, kind, result)

    monkeypatch.setattr(batch, "_assess", assess)
    record = batch.process_file(path, "FAKE-stage2-batch.pdf", 1, ["own"])
    assert calls == ["own"]
    assert observed == ["CONFLICT"]
    assert record["text_reference"]["state"] == "OK"
    assert record["document_status"] == "NEEDS_REVIEW"
    assert {"code": "MISSING_BILLING_MONTHS", "severity": "NEEDS_REVIEW"} in record["reasons"]
    assert read_document(str(path), DocType.NHIS_PAYMENT).fields["건강보험료"] == "50000"


@pytest.mark.parametrize("defect,expected", [("control", "READABLE"), ("unknown", "UNDETERMINED"),
                                            ("positive", "CONFLICT"), ("corrected", "READABLE"),
                                            ("corrected-bad-sum", "UNDETERMINED"),
                                            ("low-period", "UNDETERMINED")])
def test_independent_period_uncertainty_and_conflict_are_preserved(defect, expected):
    cells, size = base.payment(corrected=defect.startswith("corrected"))
    changed = []
    for x0, y0, x1, y1, text, confidence in cells:
        if y0 == 962 and x0 < 500 and text == "0":
            text = {"unknown": "Z", "positive": "7"}.get(defect, text)
        if defect == "corrected-bad-sum" and x0 == 738:
            text = "165,001"
        if defect == "low-period" and "납부내역" in text:
            confidence = .4
        changed.append((x0, y0, x1, y1, text, confidence))
    pages = [base.page(changed, size=size)]
    result = _from_nhis(nhis_payment.extract(pages), pages, V2DocType)
    assert json.loads(result.fields[payment_period.FIELD])["status"] == expected
    findings = _check_billing_months(result, requirement())
    if expected != "READABLE":
        assert findings and all(f.severity == "NEEDS_REVIEW" for f in findings)


def test_short_month_boxes_can_select_legacy_but_no_billing_finding_is_not_pass():
    from demo.backend.rules.doc_check import check_document
    cells, size = base.payment()
    changed = [(x0, y0, x1, y0 + 28 if text.endswith("월") and text[:-1].isdigit() else y1, text, conf)
               for x0, y0, x1, y1, text, conf in cells]
    pages = [base.page(changed, size=size)]
    extraction = nhis_payment.extract(pages)
    assert extraction.form_kind is None
    assert len(json.loads(extraction.fields["월별고지금액"].value)) == 12
    result = _from_nhis(extraction, pages, V2DocType)
    assert _check_billing_months(result, requirement()) == []
    assert check_document(requirement(), result).status == "NEEDS_REVIEW"


@pytest.mark.parametrize("shape", ["adjustment", pytest.param("clipped", marks=pytest.mark.xfail(
    strict=True, reason="C2 header-edge recovery held")), "fused"])
def test_repaired_shapes_traverse_actual_image_upload_without_changing_average(client, tmp_path, monkeypatch, shape):
    if shape == "adjustment":
        cells, size, _ = shapes.adjustment()
    else:
        cells, size = shapes.clipped_headers() if shape == "clipped" else shapes.fused_headers()
    use_own_words(monkeypatch, cells, size)
    path = image_pdf(tmp_path / "FAKE-stage2-shape.pdf", size)
    response, stored = upload(client, new_app(client, name=base.NAME, birth=base.BIRTH), path, "nhis_payment")
    assert response["status"] == "PASS"
    assert stored["fields"]["건강보험료"] == "50000"
    assert json.loads(stored["fields"]["월별고지금액"])["2025-12"] == "30000"
    assert stored["fields"]["양식판독상태"] == "완전"


@pytest.mark.parametrize("label", ["연말 정산", "연말정산액", "다른항목"])
def test_unrecognized_adjustment_stays_review_through_actual_upload(client, tmp_path, monkeypatch, label):
    cells, size, _ = shapes.adjustment(label=label)
    use_own_words(monkeypatch, cells, size)
    path = image_pdf(tmp_path / "FAKE-stage2-unknown.pdf", size)
    response, stored = upload(client, new_app(client, name=base.NAME, birth=base.BIRTH), path, "nhis_payment")
    assert response["status"] == "NEEDS_REVIEW"
    assert stored["fields"]["양식판독상태"] == "불완전"


@pytest.mark.parametrize("shape", ["adjustment", pytest.param("clipped", marks=pytest.mark.xfail(
    strict=True, reason="C2 header-edge recovery held")), "fused"])
def test_repaired_complete_table_cannot_override_independent_period_conflict(shape):
    from demo.backend.rules.doc_check import check_document
    if shape == "adjustment":
        cells, size, _ = shapes.adjustment()
    else:
        cells, size = shapes.clipped_headers() if shape == "clipped" else shapes.fused_headers()
    sum_y = next(c[1] for c in cells if c[4] == "합계")
    changed = []
    for x0, y0, x1, y1, text, confidence in cells:
        health = abs((x0 + x1) / 2 - 407) < 40
        if health and y0 == 962:
            text = "17"
        if health and y0 == sum_y:
            text = f"{int(text.replace(',', '')) + 17:,}"
        changed.append((x0, y0, x1, y1, text, confidence))
    pages = [base.page(changed, size=size)]
    extraction = nhis_payment.extract(pages)
    assert extraction.structure_complete
    result = _from_nhis(extraction, pages, V2DocType)
    assert json.loads(result.fields[payment_period.FIELD])["status"] == "CONFLICT"
    assert check_document(requirement(), result).status == "NEEDS_REVIEW"
