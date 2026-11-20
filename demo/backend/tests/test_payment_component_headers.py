"""11-19 T3 narrowing: a partly read 보수외소득월액 sub-header is never a PASS (synthetic only).

2 and 4 lost middle lines (GAP) go to review with PAYMENT_COMPONENT_HEADER_INCOMPLETE; one lost
fragment alone (FRAGMENT) only records 구성머리글불완전사유 and does not change the decision; a complete
grouped legacy form passes; 0원 and 장기요양-ratio picks still go to review for their own reason.
"""
import pytest

from demo.backend.tests.test_p2_nhis_uploads import image_pdf, use_own_words
from demo.backend.tests.test_portal_uploads import assert_upload_status, client, new_app, stored_findings, upload  # noqa: F401
from demo.backend.tools.verify_upload import SAFE_CODES
from engine_v2.tests import p2_payment_samples as sample, test_payment_amount_column as synth

from .test_payment_amount_column import CODE as AMOUNT_CODE, _monthly, _upload
from .test_payment_total_row import _marked

CODE = "PAYMENT_COMPONENT_HEADER_INCOMPLETE"


def _codes(result):
    return [finding.code for finding in result.findings]


def test_code_is_in_the_safe_vocabulary():
    assert CODE in SAFE_CODES


@pytest.mark.parametrize("layout, text", [("stacked4", "(건강)"), ("missing_under", "보수외")])
def test_one_lost_fragment_alone_is_recorded_only(tmp_path, layout, text):
    pages = _marked(synth.table(layout))
    (_, result), = pages
    result.words.remove(next(w for w in result.words if w.text == text))
    ocr, checked = _upload(tmp_path, pages)
    assert _monthly(ocr) == synth._health()
    # 11-19: FRAGMENT alone changes neither the decision nor the confidence (real government forms).
    assert checked.status == "PASS" and CODE not in _codes(checked), _codes(checked)
    assert ocr.confidence > .4 and "구성머리글상태" not in ocr.fields
    assert ocr.fields["구성머리글불완전사유"] == "FRAGMENT"


@pytest.mark.parametrize("lost", [2, 4])
def test_lost_middle_lines_go_to_review_through_actual_upload(client, tmp_path, monkeypatch, lost):  # noqa: F811
    cells, size = sample.payment()
    kept, removed = [], 0
    for cell in cells:
        if cell[4] == "소득월액" and removed < lost:
            removed += 1
        else:
            kept.append(cell)
    use_own_words(monkeypatch, kept, size)
    path = image_pdf(tmp_path / "FAKE-payment-component.pdf", size)
    response, stored = upload(client, new_app(client, name=sample.NAME, birth=sample.BIRTH), path, "nhis_payment")
    assert_upload_status(response, "NEEDS_REVIEW")
    assert CODE in [finding["code"] for finding in stored_findings(response)]
    assert stored["fields"]["구성머리글상태"] == "불완전" and stored["confidence"] <= .4
    assert stored["fields"]["구성머리글불완전사유"] == "GAP"


@pytest.mark.parametrize("layout", ["normal", "stacked4", "short4"])
def test_complete_grouped_form_passes(tmp_path, layout):
    ocr, checked = _upload(tmp_path, _marked(synth.table(layout)))
    assert checked.status == "PASS", _codes(checked)
    assert "구성머리글상태" not in ocr.fields and "구성머리글불완전사유" not in ocr.fields


@pytest.mark.parametrize("kwargs", [
    dict(layout="short4", rows={11: [0, 0, 0, 0]}),                                # 0원 in the 건강 column
    dict(layout="normal", simple=True, rows={11: [13_000]}, paid_health=100_000),  # 장기요양-sized pick
])
def test_zero_and_care_ratio_picks_still_need_review(tmp_path, kwargs):
    ocr, checked = _upload(tmp_path, _marked(synth.table(**kwargs)))
    assert checked.status == "NEEDS_REVIEW" and AMOUNT_CODE in _codes(checked)
    assert CODE not in _codes(checked)
