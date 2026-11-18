"""담당자 'AI 종합의견' — 전송 투영, 응답 검증, 대체 요약, 캐시, API.

네트워크는 쓰지 않는다. 제공자는 가짜 transport로 대신한다.
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from demo.backend import officer_summary as summary
from demo.backend.llm_client import JbaiProvider, NoneProvider, configured_provider
from demo.backend.main import app
from demo.backend.tests.test_seed_officer_demo import isolated_demo  # noqa: F401 (fixture)
from demo.backend.tools import seed_officer_demo as tool

ENV = {"PROGRAM_LLM_ENABLED": "true", "PROGRAM_LLM_PROVIDER": "jbai",
       "JBAI_BASE_URL": "https://example.invalid/open-api/v1", "JBAI_API_KEY": "sk-test-secret",
       "JBAI_LLM_MODEL": "MainModel"}

#: 개인정보를 일부러 심은 상세 응답. 실제 `review_detail` 응답과 같은 모양이다.
FORM1 = {"name": "김비밀", "birth": {"y": "1997", "m": "3", "d": "9"}, "address": "전북특별자치도 전주시 비밀로 12 (101동 202호)",
         "mobile": "010-1234-5678", "email": "secret@example.com", "accountNo": "123-456789-01234",
         "accountHolder": "김비밀", "bankName": "비밀은행", "workplaceName": "비밀상사",
         "transferIn": {"y": "2020", "m": "1", "d": "5"}, "employedAt": {"y": "2023", "m": "1", "d": "2"},
         "householdSize": "3인", "workType": "상용직"}
IDENTITY = {"name": "김비밀", "birth": "1997-03-09"}
DETAIL = {
    "name": "김비밀", "application_no": "DS-SECRET-1", "program_name": "전북청년 함께 두배적금",
    "region": "전주시", "selection": "scored",
    "ai": {"final_status": "NEEDS_REVIEW", "stage1_status": "NEEDS_REVIEW", "stage2_status": "PASS",
           "recommended_action": "담당자 재검토 필요",
           "reasons": [{"code": "LOW_OCR_CONFIDENCE", "doc_type": "주민등록초본",
                        "message": "'주민등록초본'의 일부 항목이 자동으로 판독되지 않았습니다. 김비밀 970309-1234567"}]},
    "documents": [
        {"document_id": 1, "slot_key": "resident_abstract", "label": "주민등록초본",
         "expected_doc_type": "주민등록초본", "detected_doc_type": "주민등록초본", "status": "NEEDS_REVIEW",
         "findings": [{"code": "LOW_OCR_CONFIDENCE", "severity": "NEEDS_REVIEW", "message": "일부 항목 미판독"}],
         "file_url": "/api/files/1", "bboxes": {"성명": {"page": 0}}, "ocr_confidence": 0.6,
         "extracted": {"성명": "이타인", "생년월일": "1997.03.09", "전입일": "2021-02-20", "발급일": "2026-03-05",
                       "주소": "전주시 비밀로 12", "병역사항": "복무 완료", "가구원목록": "[\"김비밀\", \"김가족\"]"}},
        {"document_id": 2, "slot_key": "work_proof", "label": "근로확인서류", "expected_doc_type": "4대보험가입내역확인서",
         "status": "PASS", "findings": [], "file_url": "/api/files/2", "ocr_confidence": 0.97,
         "extracted": {"성명": "김비밀", "생년월일": "1997-03-09", "취업일": "2023-01-02",
                       "사업장명칭목록": "[\"비밀상사\"]",
                       "가입내역": "[{\"성명\": \"김비밀\", \"사업장명칭\": \"비밀상사\", \"사업장관리번호\": \"12345678901\"}]"}},
    ],
    "eligibility": [{"key": "age", "label": "② 연령", "ok": True, "basis": "신청서 생년월일 1997-03-09 → 충족"},
                    {"key": "income", "label": "④ 소득", "ok": False, "basis": "비밀상사 고지금액 미판독"}],
    "exclusions": [{"label": "자가진단 6", "answer": "예", "ok": True}],
    "score_sheet": {"total": 80, "max_total": 100, "income_percent": 120.0, "incomplete": True,
                    "items": [{"key": "age", "label": "신청자 연령", "score": 9, "max_score": 10, "band": "25~29세",
                               "basis": "1997-03-09 출생 → 만 28세", "incomplete": False, "source_slot_key": "resident_abstract"},
                              {"key": "income", "label": "소득", "score": 0, "max_score": 40, "band": None,
                               "basis": "미판독", "incomplete": True, "source_slot_key": None}],
                    "tiebreak": [-80, 120.0, -1800, -1100, -730000], "notes": []},
    "decision": {"memo": "김비밀 010-1234-5678 통화함"},
}
SECRETS = ["김비밀", "이타인", "김가족", "1997-03-09", "1997.03.09", "970309", "1234567", "010-1234-5678",
           "secret@example.com", "123-456789-01234", "비밀은행", "비밀상사", "12345678901", "비밀로 12",
           "DS-SECRET-1", "/api/files", "복무 완료", "-730000", "통화함"]


def payload():
    return summary.summary_payload(DETAIL, FORM1, IDENTITY)


# ── 투영 ───────────────────────────────────────────────────────────────────

def test_payload_carries_no_personal_values():
    sent = json.dumps(summary.build_messages(payload()), ensure_ascii=False)
    for secret in SECRETS:
        assert secret not in sent, secret


def test_payload_keeps_explanatory_facts_as_derived_values():
    data = payload()
    resident = data["documents"][0]
    assert resident["facts"]["전입일"] == "2021-02-20"
    assert resident["facts"]["성명 대조"] == "신청자와 다름"
    assert resident["facts"]["생년월일 대조"] == "신청서와 일치"
    assert data["documents"][1]["facts"]["사업장 수"] == 1
    assert data["applicant"] == {"region": "전주시", "age_band": "25~29세", "application_form": {
        "가구원 수": "3인", "근로 형태": "상용직", "신청서 전입일": "2020-01-05", "신청서 현 직장 취업일": "2023-01-02"}}
    assert data["score_sheet"]["tiebreak"] == {"income_percent": 120.0, "residence_days": 1800, "work_days": 1100}
    assert "(생년월일) 출생" in data["score_sheet"]["items"][0]["basis"]


def test_observations_become_evidence_codes():
    codes = {item["code"] for item in payload()["evidence_codes"]}
    assert {"LOW_OCR_CONFIDENCE", "OBS_NAME_DIFFERS_RESIDENT_ABSTRACT", "OBS_TRANSFER_IN_DIFFERS",
            "ELIGIBILITY_INCOME", "SCORE_INCOME_INCOMPLETE"} <= codes
    assert "OBS_EMPLOYED_AT_DIFFERS" not in codes  # 신청서와 서류 취업일이 같다


def test_scrubber_keeps_dates_and_ordinary_sentences():
    scrub = summary._Scrubber(())
    text = "2021-02-20 전입 → 기준으로 5년 0개월, 200,000원 고지"
    assert scrub.text(text) == text
    assert scrub.text("전주시 가상시연로 12-3 거주") == "전주시 (주소) 거주"
    assert scrub.text("계좌 123-456789-01234") == "계좌 (번호)"


# ── 응답 검증 ──────────────────────────────────────────────────────────────

def answer(**overrides):
    body = {"headline": "초본 판독 확인 필요",
            "status_explanation": "서류 확인 단계가 확인필요입니다.",
            "check_points": [
                {"slot_key": "resident_abstract", "title": "초본 성명", "detail": "원본 대조", "codes": ["LOW_OCR_CONFIDENCE", "MADE_UP"]},
                {"slot_key": "nowhere", "title": "전입일", "detail": "대조", "codes": ["OBS_TRANSFER_IN_DIFFERS"]},
                {"slot_key": "work_proof", "title": "근거 없음", "detail": "추측", "codes": ["MADE_UP"]},
                {"slot_key": None, "title": "코드 없음", "detail": "추측", "codes": []},
            ],
            "document_notes": [{"slot_key": "resident_abstract", "note": "김비밀 명의 확인"},
                               {"slot_key": "resident_abstract", "note": "중복"},
                               {"slot_key": "ghost", "note": "없는 서류"}],
            "score_note": "80/100점"}
    body.update(overrides)
    return json.dumps(body, ensure_ascii=False)


def test_validate_drops_ungrounded_points_and_unknown_slots():
    data = payload()
    scrub = summary._Scrubber(summary._sensitive_literals(DETAIL, FORM1, IDENTITY))
    result = summary.validate("```json\n" + answer() + "\n```", data, scrub)
    assert [p["codes"] for p in result["check_points"]] == [["LOW_OCR_CONFIDENCE"], ["OBS_TRANSFER_IN_DIFFERS"]]
    assert result["check_points"][1]["slot_key"] is None
    assert result["document_notes"] == [{"slot_key": "resident_abstract", "note": "신청자 명의 확인"}]


@pytest.mark.parametrize("raw", [None, "", "not json", "[]", json.dumps({"headline": ""}), "{\"check_points\": []}"])
def test_validate_rejects_unusable_answers(raw):
    assert summary.validate(raw, payload()) is None


CODE_TOKEN = __import__("re").compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|\b(?:PASS|FAIL)\b")


def visible_text(result):
    """담당자 화면에 보이는 문장 전부(코드 배열 제외)."""
    parts = [result["headline"], result["status_explanation"], result["score_note"]]
    parts += [n["note"] for n in result["document_notes"]]
    for point in result["check_points"]:
        parts += [point["title"], point["detail"]] + [e["label"] + e["kind_label"] for e in point["evidence"]]
    return " ".join(parts)


def test_codes_never_reach_screen_text_and_evidence_is_plain_language():
    data = payload()
    raw = answer(headline="LOW_OCR_CONFIDENCE 때문에 NEEDS_REVIEW",
                 status_explanation="초본(LOW_OCR_CONFIDENCE, 신뢰도 0.6)이 PASS가 아님. WHATEVER_CODE 참고",
                 check_points=[{"slot_key": "resident_abstract", "title": "OBS_TRANSFER_IN_DIFFERS",
                                "detail": "전입일 확인", "codes": ["OBS_TRANSFER_IN_DIFFERS", "LOW_OCR_CONFIDENCE"]}])
    validated = summary.validate(raw, data)
    result = summary._decorate(validated, data, DETAIL)
    assert not CODE_TOKEN.search(visible_text(result)), visible_text(result)
    assert result["headline"] == "자동 판독 신뢰도 낮음 때문에 확인필요"
    point = result["check_points"][0]
    assert point["title"] == "전입일이 신청서와 다름"
    assert [(e["kind_label"], e["label"]) for e in point["evidence"]] == [
        ("자동 대조", "전입일이 신청서와 다름"), ("규칙 판정", "자동 판독 신뢰도 낮음")]


def test_check_point_points_at_the_field_to_highlight():
    detail = {**DETAIL, "documents": [{**DETAIL["documents"][0], "bboxes": {"전입일": {"page": 0}, "성명": {"page": 0}}},
                                      DETAIL["documents"][1]]}
    data = summary.summary_payload(detail, FORM1, IDENTITY)
    point = {"slot_key": "resident_abstract", "title": "t", "detail": "", "codes": ["OBS_TRANSFER_IN_DIFFERS"]}
    decorated = summary._decorate({"headline": "h", "check_points": [point, {**point, "codes": ["LOW_OCR_CONFIDENCE"]}],
                                   "document_notes": []}, data, detail)
    assert [p["field"] for p in decorated["check_points"]] == ["전입일", None]


def test_rule_summary_is_short_and_code_free():
    result = summary._decorate(summary.rule_summary(payload()), payload(), DETAIL)
    assert not CODE_TOKEN.search(visible_text(result)), visible_text(result)
    assert len(result["headline"]) <= 60 and all(len(p["title"]) <= 24 for p in result["check_points"])


def test_rule_summary_has_screen_shape_and_grounded_codes():
    data = payload()
    result = summary.rule_summary(data)
    codes = {item["code"] for item in data["evidence_codes"]}
    assert result["headline"].startswith("확인필요")
    assert result["check_points"] and all(set(p["codes"]) <= codes for p in result["check_points"])
    assert {n["slot_key"] for n in result["document_notes"]} == {"resident_abstract", "work_proof"}
    assert "80/100점" in result["score_note"]


# ── 제공자 ─────────────────────────────────────────────────────────────────

class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return {"choices": [{"message": {"content": item}, "finish_reason": "stop"}]}


def test_provider_requires_explicit_opt_in():
    assert isinstance(configured_provider(environ={**ENV, "PROGRAM_LLM_ENABLED": ""}), NoneProvider)
    assert isinstance(configured_provider(environ={**ENV, "JBAI_API_KEY": ""}), NoneProvider)
    assert isinstance(configured_provider(environ={**ENV, "JBAI_BASE_URL": "http://insecure"}), NoneProvider)
    provider = configured_provider(environ=ENV)
    assert isinstance(provider, JbaiProvider) and "sk-test" not in repr(provider)


def test_provider_falls_back_to_prompt_mode_once_and_logs_without_secrets(caplog):
    from urllib.error import HTTPError
    transport = FakeTransport(HTTPError("u", 400, "bad", {}, None), answer())
    provider = configured_provider(environ=ENV, transport=transport)
    with caplog.at_level(logging.INFO, logger="demo.backend.llm"):
        text = provider.generate("officer_summary", summary.build_messages(payload()))
    assert text == answer()
    assert transport.calls[0]["body"]["response_format"] == {"type": "json_object"}
    assert "response_format" not in transport.calls[1]["body"]
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer sk-test-secret"
    logged = caplog.text
    assert "outcome=http_4xx" in logged and "outcome=ok" in logged
    assert "sk-test" not in logged and "example.invalid" not in logged and "주민등록초본" not in logged


def test_provider_does_not_retry_timeouts():
    transport = FakeTransport(TimeoutError())
    provider = configured_provider(environ=ENV, transport=transport)
    assert provider.generate("officer_summary", summary.build_messages(payload())) is None
    assert len(transport.calls) == 1


# ── 캐시 + API (격리 DB) ───────────────────────────────────────────────────

def seeded(capsys):
    assert tool.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    return out["applications"]["needs-review"]["application_id"]


def test_summary_is_cached_until_input_changes(isolated_demo, capsys):
    from demo.backend.api.common import load_application
    from demo.backend.api.officer import review_detail
    aid = seeded(capsys)
    detail, application = review_detail(aid, "province"), load_application(aid)
    transport = FakeTransport(answer(), answer(headline="두 번째"), answer(headline="세 번째"))
    provider = configured_provider(environ=ENV, transport=transport)

    def run(detail_value, **kwargs):
        return summary.summarize(aid, detail_value, application.form1_json, application.identity_json,
                                 provider=provider, **kwargs)

    first = run(detail)
    assert first["source"] == "jbai" and first["cached"] is False and first["label"] == summary.LABEL
    again = run(detail)
    assert again["cached"] is True and again["headline"] == first["headline"] and len(transport.calls) == 1
    changed = {**detail, "ai": {**detail["ai"], "final_status": "FAIL"}}
    assert run(changed)["headline"] == "두 번째"
    assert run(changed, force=True)["headline"] == "세 번째"
    assert len(transport.calls) == 3
    sent = json.dumps([call["body"] for call in transport.calls], ensure_ascii=False)
    assert application.form1_json["name"] not in sent and application.application_no not in sent


def test_failed_generation_returns_rules_without_storing(isolated_demo, capsys):
    from sqlmodel import select
    from demo.backend import models
    from demo.backend.api.common import load_application
    from demo.backend.api.officer import review_detail
    aid = seeded(capsys)
    detail, application = review_detail(aid, "province"), load_application(aid)
    transport = FakeTransport("not json", "still not json")
    provider = configured_provider(environ=ENV, transport=transport)
    clock = iter([0.0, 10.0, 500.0]).__next__
    first = summary.summarize(aid, detail, application.form1_json, application.identity_json,
                              provider=provider, clock=clock)
    assert first["source"] == "rules" and first["label"] == "규칙 기반 요약" and first["check_points"]
    # 실패 직후 같은 입력이면 제공자를 다시 부르지 않는다.
    summary.summarize(aid, detail, application.form1_json, application.identity_json, provider=provider, clock=clock)
    assert len(transport.calls) == 2  # json_object + prompt 재시도 한 번
    with models.get_session() as s:
        assert s.exec(select(models.ReviewSummary)).all() == []


def test_worker_prefetches_in_arrival_order_then_only_changes(isolated_demo, capsys, monkeypatch):
    from datetime import datetime, timedelta
    from sqlmodel import select
    from demo.backend import models
    assert tool.main([]) == 0
    capsys.readouterr()
    # 접수 순서를 id와 반대로 만들어, id가 아니라 submitted_at을 따르는지 본다.
    with models.get_session() as s:
        apps = s.exec(select(models.Application).order_by(models.Application.id)).all()
        base = datetime(2026, 3, 3, 9)
        for offset, row in enumerate(reversed(apps)):
            row.submitted_at = base + timedelta(minutes=offset)
            s.add(row)
        s.commit()
        expected = [row.id for row in reversed(apps)]

    seen = []
    original = summary.summarize

    def recording(application_id, *args, **kwargs):
        seen.append(application_id)
        return original(application_id, *args, **kwargs)

    monkeypatch.setattr(summary, "summarize", recording)
    transport = FakeTransport(*[answer()] * 10)
    worker = summary.SummaryWorker(provider=configured_provider(environ=ENV, transport=transport), pause=0)

    assert worker.run_once() == len(expected)
    assert seen == expected and len(transport.calls) == len(expected)
    # 두 번째 바퀴: 전부 캐시와 같아 호출이 없다.
    assert worker.run_once() == 0 and len(transport.calls) == len(expected)
    # 판정이 바뀐 건만 다시 만든다.
    with models.get_session() as s:
        review = s.exec(select(models.Review).where(models.Review.application_id == expected[0])).first()
        review.final_status = "FAIL"
        s.add(review)
        s.commit()
    assert worker.run_once() == 1 and len(transport.calls) == len(expected) + 1


def test_worker_does_not_start_without_llm(monkeypatch):
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    worker = summary.SummaryWorker()
    assert worker.start() is False and worker.run_once() == 0
    assert summary.worker_enabled({}) and not summary.worker_enabled({"OFFICER_SUMMARY_PREFETCH": "false"})


def test_summary_api(isolated_demo, capsys, monkeypatch):
    aid = seeded(capsys)
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    with TestClient(app) as client:
        response = client.get(f"/api/officer/applications/{aid}/summary", params={"role": "province"})
        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "rules" and body["headline"]
        assert {"status_explanation", "check_points", "document_notes", "score_note", "generated_at"} <= body.keys()
        assert client.post(f"/api/officer/applications/{aid}/summary", params={"role": "province"}).status_code == 200
        assert client.get(f"/api/officer/applications/{aid}/summary", params={"role": "nobody"}).status_code == 400
        assert client.get("/api/officer/applications/999999/summary").status_code == 404
