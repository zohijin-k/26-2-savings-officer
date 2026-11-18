"""11-19: a 고지금액 that may come from the 장기요양 column (or a 0원 pick) never passes (synthetic only).

The document goes to review (PAYMENT_AMOUNT_COLUMN_UNCERTAIN) and the income decision is withheld
(PREMIUM_UNTRUSTED); the read values are not replaced.
"""
import json
import os
from datetime import date
from unittest.mock import patch

import pytest

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tests import test_payment_amount_column as synth

from ..ocr.localocr import ENGINE_ENV, LocalOcr
from ..rules.doc_check import check_document
from ..rules.doc_types import DocType
from ..rules.facts import DEFAULT_PAYMENT_MONTHS, build_facts
from ..rules.identity import Identity
from ..rules.required_docs import DocRequirement
from ..rules.scoring import score_income
from .run_p8_localocr_scenarios import make_image_pdf
from .test_income_facts import documents

IDENTITY = Identity("가상시험", date(1999, 1, 1))
CODE = "PAYMENT_AMOUNT_COLUMN_UNCERTAIN"


def _slot():
    return DocRequirement(slot_key="nhis_payment", doc_type=DocType.NHIS_PAYMENT, label="가짜 납부확인서",
                          min_issue_date=date(2026, 3, 3), premium_months=list(DEFAULT_PAYMENT_MONTHS))


def _upload(tmp_path, pages):
    from engine_v2.pipeline import ocr as v2ocr

    (_, result), = pages
    path = make_image_pdf(tmp_path / "synthetic-payment.pdf", pages=1)

    def recognize(png, size):
        sx, sy = size[0] / synth.W, size[1] / synth.H
        return [OcrWord(w.text, w.confidence, (w.bbox_px[0] * sx, w.bbox_px[1] * sy,
                                               w.bbox_px[2] * sx, w.bbox_px[3] * sy)) for w in result.words]
    with patch.dict(os.environ, {ENGINE_ENV: "pay-synthetic"}), \
            patch.dict(v2ocr.ENGINES, {"pay-synthetic": recognize}):
        ocr = LocalOcr().read(str(path), None)
    assert ocr is not None and ocr.detected_doc_type is DocType.NHIS_PAYMENT
    return ocr, check_document(_slot(), ocr, identity=IDENTITY)


def _monthly(ocr):
    raw = ocr.fields.get("월별고지금액")
    return [json.loads(raw).get(m) for m in DEFAULT_PAYMENT_MONTHS] if raw else [None] * 3


def _income(ocr, result):
    docs = documents()
    docs[1] = {"doc_type": str(DocType.NHIS_PAYMENT), "document_id": 202, "status": result.status,
               "confidence": ocr.confidence, "fields": dict(ocr.fields), "bboxes": {}}
    facts = build_facts({}, docs)
    return facts, score_income(facts)


@pytest.mark.parametrize("zero", [False, True])
@pytest.mark.parametrize("layout, align", [("short4", "right"), ("missing_under", "right"),
                                           ("sum_column", "right"), ("fused4", "center"), ("misread", "right")])
def test_reproduced_layouts_never_pass_with_the_care_amount(tmp_path, layout, align, zero):
    ocr, result = _upload(tmp_path, synth.table(layout, zero=zero, align=align))
    assert _monthly(ocr) != synth._care_values(zero)
    assert result.status != "PASS"
    facts, income = _income(ocr, result)
    assert facts.monthly_premium is None and income.status == "UNDETERMINED"


def test_guarded_upload_is_reviewed_with_the_reason_and_values_kept(tmp_path):
    ocr, result = _upload(tmp_path, synth.table("normal", simple=True, rows={11: [0]}))
    assert ocr.fields["월별고지금액상태"] == "불확실" and ocr.fields["월별고지금액불확실사유"] == "ZERO_AMOUNT"
    assert _monthly(ocr)[1] == "0"
    assert result.status == "NEEDS_REVIEW" and CODE in result.codes
    finding = next(f for f in result.findings if f.code == CODE)
    assert finding.severity == "NEEDS_REVIEW" and "ZERO_AMOUNT" in finding.detail
    facts, income = _income(ocr, result)
    assert facts.premium_reason_code == "PREMIUM_UNTRUSTED" and income.status == "UNDETERMINED"


@pytest.mark.parametrize("kwargs, code", [
    (dict(simple=True, rows={11: [13_000]}, paid_health=100_000), "CARE_RATIO"),
    (dict(simple=True, header_conf=.5), "HEADER_UNCERTAIN"),
    (dict(paid_health=150_000), "LARGER_HEALTH")])
def test_each_guard_reviews_and_withholds_income(tmp_path, kwargs, code):
    ocr, result = _upload(tmp_path, synth.table("normal", **kwargs))
    assert code in ocr.fields["월별고지금액불확실사유"].split(",")
    assert result.status == "NEEDS_REVIEW" and CODE in result.codes
    assert _income(ocr, result)[1].status == "UNDETERMINED"


def test_normal_upload_is_unchanged(tmp_path):
    ocr, result = _upload(tmp_path, synth.table("normal"))
    assert _monthly(ocr) == synth._health() and "월별고지금액상태" not in ocr.fields
    assert CODE not in result.codes


@pytest.mark.parametrize("value", ["0", "12950"])
def test_application_income_never_passes_on_an_uncertain_amount_even_if_status_is_stale(value):
    """A stored PASS from before the guard cannot let an uncertain 0원 or 장기요양 amount decide income."""
    docs = documents(premium=value)
    docs[1]["fields"]["월별고지금액상태"] = "불확실"
    facts = build_facts({}, docs)
    assert facts.monthly_premium is None and facts.premium_reason_code == "PREMIUM_UNTRUSTED"
    assert score_income(facts).status == "UNDETERMINED"
    del docs[1]["fields"]["월별고지금액상태"]
    assert build_facts({}, docs).monthly_premium == int(value)
