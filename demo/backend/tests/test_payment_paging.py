"""Independent payment folios: authored words, actual PDFs and verdict boundaries."""
from copy import deepcopy
import json

import pytest

from demo.backend.ocr import read_document
from demo.backend.ocr.localocr import _from_nhis
from demo.backend.rules.doc_check import check_document
from demo.backend.tests.test_payment_failure_certainty import requirement
from demo.backend.tests.test_portal_uploads import client
from engine_v2.extractors import nhis_payment
from engine_v2.pipeline.preprocess import PageSource
from engine_v2.schemas.models import DocType as V2DocType
from engine_v2.tests import p2_payment_samples as base
from engine_v2.tests.test_income_payment_evidence import _text_pdf

FIELD = "납부쪽표기자료"
UNCERTAIN = "NHIS_PAYMENT_PAGING_UNCERTAIN"


def pages(marker="1/1", confidence=1, broken_table=False, text=False):
    cells, size = base.payment()
    if broken_table:
        cells = [c for c in cells if not (c[4] == "소득월액" and c[0] > 1700)]
    if marker is not None:
        cells.append(base.cell(1770, 35, 1930, 82, marker, confidence))
    page, words = base.page(cells, size=size)
    if text:
        page.source = PageSource.TEXT_LAYER
        words.engine = "text_layer"
    return [(page, words)]


def assess(input_pages):
    result = _from_nhis(nhis_payment.extract(input_pages), input_pages, V2DocType)
    return result, check_document(requirement(), result)


@pytest.mark.parametrize("text", [False, True])
@pytest.mark.parametrize("broken_table", [False, True])
def test_certain_missing_folio_fails_independently_of_table_and_document_confidence(text, broken_table):
    ocr, verdict = assess(pages("1/2", broken_table=broken_table, text=text))
    assert verdict.status == "FAIL"
    assert any(f.code == "PAGES_INCOMPLETE" and f.severity == "FAIL" for f in verdict.findings)


@pytest.mark.parametrize("text", [False, True])
def test_complete_marker_retains_normal_payment_pass(text):
    _, verdict = assess(pages(text=text))
    assert verdict.status == "PASS"


@pytest.mark.parametrize("marker,confidence", [(None, 1), ("1/", 1), ("l/2", 1), ("1/2", .2), ("0/2", 1)])
@pytest.mark.parametrize("text", [False, True])
def test_uncertain_marker_is_review_without_reupload_or_quality_failure(marker, confidence, text):
    ocr, _ = assess(pages(marker, confidence, text=text))
    ocr.image_quality = .55
    verdict = check_document(requirement(), ocr)
    assert verdict.status == "NEEDS_REVIEW"
    assert UNCERTAIN not in verdict.codes
    assert "LOW_IMAGE_QUALITY" in verdict.codes
    assert not any(f.severity == "FAIL" for f in verdict.findings)
    assert next(f for f in verdict.findings if f.code == "LOW_IMAGE_QUALITY").severity == "NEEDS_REVIEW"


@pytest.mark.parametrize("marker,confidence", [(None, 1), ("1/", 1), ("l/2", 1), ("1/2", .2), ("0/2", 1)])
@pytest.mark.parametrize("text", [False, True])
def test_uncertain_marker_with_incomplete_table_keeps_paging_review_without_reupload(marker, confidence, text):
    ocr, _ = assess(pages(marker, confidence, broken_table=True, text=text))
    ocr.image_quality = .95
    verdict = check_document(requirement(), ocr)
    assert verdict.status == "NEEDS_REVIEW"
    assert UNCERTAIN in verdict.codes
    assert "LOW_IMAGE_QUALITY" not in verdict.codes
    assert not any(f.severity == "FAIL" for f in verdict.findings)
    finding = next(f for f in verdict.findings if f.code == UNCERTAIN)
    assert not any(word in finding.how_to_fix for word in ["다시", "촬영", "재업로드", "재발급"])


def test_body_fraction_cannot_establish_missing_page():
    input_pages = pages(None)
    from engine_v2.pipeline.ocr import OcrWord
    input_pages[0][1].words.append(OcrWord("1/8", 1, (1700, 1900, 1880, 1950)))
    _, verdict = assess(input_pages)
    assert "PAGES_INCOMPLETE" not in verdict.codes


@pytest.mark.parametrize("marker", ["1/1", "1/2"])
def test_actual_text_pdf_upload_route_checks_printed_total(tmp_path, monkeypatch, marker):
    cells, size = base.payment()
    cells.append(base.cell(1770, 35, 1930, 82, marker, 1))
    path = _text_pdf(tmp_path / "FAKE-payment-folio.pdf", cells, size)
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    from demo.backend.rules.doc_types import DocType
    ocr = read_document(str(path), DocType.NHIS_PAYMENT)
    verdict = check_document(requirement(), ocr)
    assert verdict.status == ("PASS" if marker == "1/1" else "FAIL")
    assert ("PAGES_INCOMPLETE" in verdict.codes) == (marker == "1/2")


def test_collector_keeps_missing_required_and_verified_markerless_distinct():
    from engine_v2.extractors import payment_paging
    required = payment_paging.collect(pages(None), policy="REQUIRED")
    optional = payment_paging.collect(pages(None), policy="NOT_REQUIRED")
    assert payment_paging.assess(required) == "UNCERTAIN"
    assert payment_paging.assess(optional) == "NOT_REQUIRED"


@pytest.mark.parametrize("defect", ["boolean-count", "bad-confidence", "conflicting-total", "wrong-indices", "malformed"])
def test_malformed_cached_paging_never_proves_missing_pages(defect):
    from engine_v2.extractors import payment_paging
    evidence = payment_paging.collect(pages("1/2"))
    if defect == "boolean-count":
        evidence["uploaded_page_count"] = True
    elif defect == "bad-confidence":
        evidence["marker_confidences"] = [float("nan")]
    elif defect == "conflicting-total":
        evidence["expected_total"] = 3
    elif defect == "wrong-indices":
        evidence["form_page_indices"] = [8]
    else:
        evidence = {"version": 1}
    assert payment_paging.assess(evidence) == "UNCERTAIN"


def test_other_document_paging_behavior_is_not_changed():
    from demo.backend.ocr.base import OcrResult
    from demo.backend.rules.doc_types import DocType
    ocr = OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT, confidence=1,
                    fields={FIELD: json.dumps({"version": 1})}, tier="fixture")
    verdict = check_document(requirement(DocType.RESIDENT_ABSTRACT), ocr)
    assert UNCERTAIN not in verdict.codes


def test_split_marker_keeps_all_observed_tokens():
    from engine_v2.extractors import payment_paging
    from engine_v2.pipeline.ocr import OcrWord
    input_pages = pages(None)
    for index, token in enumerate(["1", "/", "2"]):
        input_pages[0][1].words.append(OcrWord(token, 1, (1770 + index * 50, 35, 1815 + index * 50, 82)))
    assert payment_paging.assess(payment_paging.collect(input_pages)) == "INCOMPLETE"


def test_crossing_marker_cannot_be_cropped_into_count_proof():
    from engine_v2.extractors import payment_paging
    from engine_v2.pipeline.ocr import OcrWord
    input_pages = pages(None)
    token = OcrWord("1/2", 1, (1310, 35, 1380, 82))
    input_pages[0][1].words.append(token)
    assert payment_paging.assess(payment_paging.collect(input_pages)) == "UNCERTAIN"
    assert token.text == "1/2"
    assert token.bbox_px == (1310, 35, 1380, 82)


@pytest.mark.parametrize("markers,expected", [(["1/2", "2/2"], "COMPLETE"),
    (["1/2", "2/3"], "UNCERTAIN"), (["1/2", "1/2"], "UNCERTAIN"),
    (["1/3", None], "INCOMPLETE"), ([None, None], "UNCERTAIN")])
def test_multiple_pages_are_independent_of_monthly_table(markers, expected):
    from engine_v2.extractors import payment_paging
    input_pages = []
    for index, marker in enumerate(markers):
        page, result = pages(marker)[0]
        page.page = index
        input_pages.append((page, result))
    assert payment_paging.assess(payment_paging.collect(input_pages)) == expected


def test_additional_attachment_does_not_replace_missing_form_page():
    from engine_v2.extractors import payment_paging
    evidence = payment_paging.collect(pages("1/2"), uploaded_page_count=2)
    assert evidence["form_page_indices"] == [0]
    assert payment_paging.assess(evidence) == "INCOMPLETE"


@pytest.mark.parametrize("stage", ["own", "reference"])
def test_exact_v2_s1_pages_incomplete_is_fail_in_both_paths(tmp_path, monkeypatch, stage):
    from engine_v2.tools import documentai_corpus_v2 as corpus, documentai_staged as staged
    from engine_v2.pipeline import ocr
    source = next(s for s in corpus.sources(0) if s.doc == "nhis_payment")
    damaged = next(s for label, s in corpus.legacy.defects(source) if label == "pages_incomplete")
    image, reference, _ = corpus.rendered(damaged)
    path = tmp_path / "FAKE-v2-s1.png"
    image.save(path)
    # Authored deterministic words exercise own routing. The separate native
    # target run and full 410-pair measurement verify actual own recognition.
    monkeypatch.setitem(ocr.ENGINES, "own", lambda *_: deepcopy(reference))
    result = staged.measure_stage(path, "nhis_payment", damaged.truth, identity=damaged.identity,
        reference_words=reference if stage == "reference" else None)
    assert result["failed"] == "X"
    assert result["status"] == "FAIL"
    assert "PAGES_INCOMPLETE" in result["confirmed_reupload_codes"]


@pytest.mark.parametrize("marker,status", [("1/1", "PASS"), ("1/2", "FAIL"), (None, "PASS")])
def test_actual_image_upload_persists_independent_paging(client, tmp_path, monkeypatch, marker, status):
    from demo.backend.tests.test_p2_nhis_uploads import image_pdf, use_own_words
    from demo.backend.tests.test_portal_uploads import new_app, upload
    cells, size = base.payment()
    if marker is not None:
        cells.append(base.cell(1770, 35, 1930, 82, marker, 1))
    use_own_words(monkeypatch, cells, size)
    path = image_pdf(tmp_path / "FAKE-paging-upload.pdf", size)
    response, stored = upload(client, new_app(client, name=base.NAME, birth=base.BIRTH), path, "nhis_payment")
    assert response["status"] == status
    assert FIELD in stored["fields"]


def test_verified_markerless_form_keeps_nonpaging_assessment():
    from engine_v2.extractors import payment_paging
    ocr, _ = assess(pages(None))
    ocr.fields[FIELD] = json.dumps(payment_paging.collect(pages(None), policy="NOT_REQUIRED"))
    assert check_document(requirement(), ocr).status == "PASS"


@pytest.mark.parametrize("marker", [None, "1/2"])
def test_paging_review_or_failure_cannot_establish_income(marker):
    from demo.backend.rules.facts import _field
    from demo.backend.rules.doc_types import DocType
    ocr, verdict = assess(pages(marker))
    record = {"doc_type": str(DocType.NHIS_PAYMENT), "fields": ocr.fields, "confidence": ocr.confidence,
              "status": verdict.status}
    assert ocr.fields["건강보험료"] == "50000"
    assert _field(record, "건강보험료") == ("50000" if marker is None else None)
    assert _field(record, "성명") == base.NAME


@pytest.mark.parametrize("marker,expected", [("1/2", "FAIL"), (None, "NEEDS_REVIEW")])
def test_api_list_and_final_check_keep_paging_severity(client, tmp_path, monkeypatch, marker, expected):
    from demo.backend.tests.test_income_review import make_application
    from demo.backend.tests.test_eligibility_blockers import ready
    from demo.backend.api import documents
    from PIL import Image
    application = ready(make_application(premium=0))
    ocr, _ = assess(pages(marker))
    # Isolate the page decision from the fixture application's identity/date.
    ocr.fields.update({"성명": "가상신청", "생년월일": "1999-01-01", "발급일": "2026-04-07"})
    from datetime import date
    ocr.issue_date = date(2026, 4, 7)
    monkeypatch.setattr(documents, "read_document", lambda *_: deepcopy(ocr))
    path = tmp_path / "FAKE-final-paging.png"
    Image.new("RGB", (1600, 2200), "white").save(path)
    response = client.post(f"/api/applications/{application.id}/documents",
        files={"file": (path.name, path.read_bytes(), "image/png")},
        data={"slot_key": "nhis_payment", "declared_issue_date": "2026-04-07"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected
    listed = client.get(f"/api/applications/{application.id}/documents").json()
    assert next(r for r in listed if r["document_id"] == body["document_id"])["status"] == expected
    final = client.get(f"/api/applications/{application.id}/final-check").json()
    blocking = [r for r in final["blockers"] if r["kind"] == "document" and r["target"] == "nhis_payment"]
    assert bool(blocking) is (expected == "FAIL")
