"""Officer counts, grounded jumps, cache and mocked-provider privacy."""
import json

import pytest

from demo.backend import officer_summary as summary
from demo.backend.llm_client import configured_provider
from demo.backend.rules.doc_check import check_document
from demo.backend.tests.test_insurance_portal import req
from demo.backend.tests.test_insurance_workplace_consistency import converted
from demo.backend.tests.test_officer_summary import ENV, FakeTransport, answer
from engine_v2.extractors import insurance_workplace as contract
from engine_v2.tests.test_insurance_workplace_consistency import NAME, OTHER, NUMBER


def detail(conflict=True):
    ocr = converted(conflict=conflict)
    result = check_document(req(), ocr)
    return {"name": "가상신청", "region": "전주시", "documents": [{"slot_key": "work_proof",
        "label": "근로확인서류", "expected_doc_type": "4대보험가입내역확인서",
        "status": result.status, "findings": [f.as_dict() for f in result.findings],
        "extracted": ocr.fields, "bboxes": {key: box.as_dict() for key, box in ocr.bboxes.items()}}],
        "ai": {"final_status": result.status, "reasons": []}, "eligibility": [], "score_sheet": {}}


def test_J_uncertain_count_is_not_reported_as_a_business_total():
    data = summary.summary_payload(detail())
    facts = data["documents"][0]["facts"]
    assert facts["사업장 수 확인"] == "명칭 불일치로 미확정"
    assert "사업장 수" not in facts and "판독된 사업장 명칭 수" not in facts
    assert contract.CODE in {item["code"] for item in data["evidence_codes"]}


def test_J_fresh_name_list_is_qualified_and_historical_markerless_behavior_preserved():
    d = detail(False)
    facts = summary.summary_payload(d)["documents"][0]["facts"]
    assert facts["판독된 사업장 명칭 수"] == 1
    assert "사업장 수" not in facts
    del d["documents"][0]["extracted"][contract.COUNT_FIELD]
    assert summary.summary_payload(d)["documents"][0]["facts"]["사업장 수"] == 1


def test_J_unknown_fresh_count_marker_cannot_fall_back_to_asserted_count():
    d = detail(False)
    d["documents"][0]["extracted"][contract.COUNT_FIELD] = "FAKE_UNKNOWN"
    facts = summary.summary_payload(d)["documents"][0]["facts"]
    assert "사업장 수" not in facts and "판독된 사업장 명칭 수" not in facts


def test_B_grounded_reason_jumps_to_observed_name_words():
    d = detail(); payload = summary.summary_payload(d)
    result = summary._decorate(summary.rule_summary(payload), payload, d)
    points = [point for point in result["check_points"] if contract.CODE in point["codes"]]
    assert points and points[0]["field"] == contract.STATE_FIELD
    assert points[0]["evidence"][0]["label"] == "같은 관리번호의 사업장 명칭 불일치"
    assert summary.CODE_FIELDS[contract.CODE][0] in d["documents"][0]["bboxes"]


def test_N_external_provider_receives_no_names_numbers_raw_rows_or_proof():
    d = detail(); payload = summary.summary_payload(d)
    transport = FakeTransport(answer())
    provider = configured_provider(environ=ENV, transport=transport)
    provider.generate("officer_summary", summary.build_messages(payload))
    sent = json.dumps([call["body"] for call in transport.calls], ensure_ascii=False)
    proof = json.loads(d["documents"][0]["extracted"][contract.PROOF_FIELD])
    for secret in (NAME, OTHER, NUMBER, "가상신청", proof["rows_sha256"], d["documents"][0]["extracted"]["가입내역"], contract.PROOF_FIELD):
        assert secret not in sent


def test_J_projection_version_invalidates_old_summary_hash(monkeypatch):
    payload = summary.summary_payload(detail())
    provider = configured_provider(environ=ENV, transport=FakeTransport(answer()))
    current = summary.input_hash(payload, provider)
    assert summary.SUMMARY_VERSION > 3
    monkeypatch.setattr(summary, "SUMMARY_VERSION", 3)
    assert current != summary.input_hash(payload, provider)
