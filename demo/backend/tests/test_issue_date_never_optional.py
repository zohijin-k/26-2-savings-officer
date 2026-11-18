"""5b: with the default criteria the six issue-dated forms can never PASS without an issue date.

A criteria edit that sets a slot's issue rule to mode 'none' (or another date basis) turns the issue-date
check off on purpose; that policy path is documented, not tested here.
"""
from datetime import date

import pytest

from ..api.common import checklist_from_inputs
from ..ocr.base import OcrResult
from ..rules.criteria import default_criteria
from ..rules.doc_check import check_document
from ..rules.doc_types import DocType
from ..rules.programs import DOUBLE_SAVINGS, JOB_PACKAGE, get_program
from ..rules.required_docs import ApplicantDocInput, WorkCategory

SIX = (DocType.RESIDENT_ABSTRACT, DocType.RESIDENT_CERTIFICATE, DocType.NHIS_PAYMENT,
       DocType.NHIS_QUALIFICATION, DocType.NHIS_ACQUISITION_LOSS, DocType.INSURANCE_4)
TIERS = ("localocr", "jbai", "upstage", "pdftext")
ISSUE_CODES = {"ISSUE_DATE_MISSING", "REQUIRED_FIELD_UNREADABLE"}


def _slots():
    slots = []
    for code in (DOUBLE_SAVINGS, JOB_PACKAGE):
        program, criteria = get_program(code), default_criteria(code)
        start = date.fromisoformat(criteria["application_period"][0])
        for category in (None, *WorkCategory):
            for req in checklist_from_inputs(program, ApplicantDocInput(work_category=category), criteria, start):
                if req.upload and any(req.accepts(kind) for kind in SIX):
                    slots.append(req)
    return slots


SLOTS = _slots()


def test_every_default_slot_for_the_six_forms_has_an_issue_rule():
    assert {req.doc_type for req in SLOTS} >= {DocType.RESIDENT_ABSTRACT, DocType.NHIS_PAYMENT,
                                                DocType.NHIS_QUALIFICATION, DocType.NHIS_ACQUISITION_LOSS,
                                                DocType.INSURANCE_4}
    for req in SLOTS:
        assert req.date_basis == "issue_date"
        assert req.min_issue_date is not None or req.max_issue_date is not None
    # No slot accepts a 주민등록등본; it can only be a wrong document there.
    assert not any(req.accepts(DocType.RESIDENT_CERTIFICATE) for req in SLOTS)


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("req", SLOTS, ids=lambda req: req.slot_key)
def test_missing_issue_date_never_passes(req, tier):
    for kind in SIX:
        ocr = OcrResult(detected_doc_type=kind, confidence=.95, image_quality=.95, tier=tier,
                        fields={"성명": "가상시험", "생년월일": "1990-01-01"})
        result = check_document(req, ocr)
        assert result.status != "PASS", (req.slot_key, kind, tier)
        if req.accepts(kind):
            assert ISSUE_CODES & set(result.codes), (req.slot_key, kind, tier, result.codes)
