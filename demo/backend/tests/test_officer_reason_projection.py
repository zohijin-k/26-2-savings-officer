"""11-27: 신청 단위 확인 사유가 서류별 실제 사유와 일치해야 한다 (합성 데이터만).

수정 전: 엔진 1단계가 저장 판정 NEEDS_REVIEW 서류를 모두 LOW_OCR_CONFIDENCE("일부 항목이 자동으로
판독되지 않았습니다")로 기록했고, 담당자 신청 요약·AI 종합의견은 그 문장을 그대로 보였다. 판독 신뢰도 0.95인
스캔 초본(SCAN_UNVERIFIED)도 "자동 판독 신뢰도 낮음"으로 보였다.
"""
import json
from copy import deepcopy

import pytest
from sqlmodel import select

from demo.backend import models
from demo.backend.review_reasons import SCAN_COMPLETENESS_EXPLANATION, SCAN_COMPLETENESS_TITLE, project_reasons
from demo.backend.tests.security_support import authenticate_officer, claim_synthetic_application
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_portal_uploads import client  # noqa: F401  (fixture)

ENGINE_LOW = "'{}'의 일부 항목이 자동으로 판독되지 않았습니다. 담당자가 직접 확인할 예정입니다."


def low(doc_type):
    return {"stage": "stage1_document", "code": "LOW_OCR_CONFIDENCE", "message": ENGINE_LOW.format(doc_type),
            "doc_type": doc_type}


def doc(doc_type, *, status="NEEDS_REVIEW", confidence=.95, findings=(), extracted=None, document_id=1,
        detected=True):
    return {"document_id": document_id, "slot_key": f"slot-{document_id}", "expected_doc_type": doc_type,
            "detected_doc_type": doc_type if detected else None, "status": status, "ocr_confidence": confidence,
            "findings": list(findings), "extracted": extracted or {}}


def finding(code, severity="NEEDS_REVIEW", message="합성 저장 사유입니다."):
    return {"code": code, "severity": severity, "message": message}


SCAN_DOC = doc("주민등록초본", findings=[finding(
    "ADDRESS_HISTORY_INCOMPLETE", message="초본 주소 이력 일부를 읽지 못했을 수 있습니다. 전입일과 주소 이력은 담당자가 원본에서 확인합니다.")],
    extracted={"주소이력상태": "불확실", "주소이력불확실사유": "SCAN_UNVERIFIED", "주소이력끝근거": "이하 여백 (3쪽)"})


def test_scan_abstract_is_completeness_not_ocr_confidence():
    reasons = [low("주민등록초본")]
    before = deepcopy(reasons), deepcopy(SCAN_DOC)
    [item] = project_reasons(reasons, [SCAN_DOC])
    assert item["code"] == "ADDRESS_HISTORY_INCOMPLETE" and item["severity"] == "NEEDS_REVIEW"
    assert item["category"] == "completeness" and item["category_label"] == "서류 완결성 확인 필요"
    assert item["title"] == SCAN_COMPLETENESS_TITLE
    assert item["message"] == SCAN_COMPLETENESS_EXPLANATION
    assert "판독" not in item["title"] + item["message"] and "신뢰도" not in item["title"] + item["message"]
    assert "누락" not in item["title"] + item["message"]  # 오류가 확정된 것처럼 단정하지 않는다.
    assert item["origin"] == {"code": "LOW_OCR_CONFIDENCE", "message": ENGINE_LOW.format("주민등록초본")}
    assert item["stored_message"].startswith("초본 주소 이력 일부를")
    assert item["details"] == ["스캔 초본은 주소이력 끝부분까지 제출됐는지 자동으로 확정하지 않음"]
    assert item["document_id"] == 1 and item["priority"] == 1
    assert (reasons, SCAN_DOC) == before  # 저장값·입력은 바꾸지 않는다.


def test_high_ocr_confidence_never_hides_completeness_review():
    confident = {**SCAN_DOC, "ocr_confidence": .99}
    [item] = project_reasons([low("주민등록초본")], [confident])
    assert item["category"] == "completeness" and item["severity"] == "NEEDS_REVIEW"


@pytest.mark.parametrize("sub,title", [
    ("END_UNCONFIRMED,SCAN_UNVERIFIED", "주소이력 끝 표시 미확인"),
    ("NUMBER_GAP,SCAN_UNVERIFIED", "주소이력 일부 판독 불완전"),
    ("", "주소이력 완전성 확인 필요"),
])
def test_address_history_sub_reasons(sub, title):
    source = {**SCAN_DOC, "extracted": {"주소이력불확실사유": sub}}
    [item] = project_reasons([low("주민등록초본")], [source])
    assert item["title"] == title and item["category"] == "completeness"


def test_unknown_type_missing_field_and_true_low_ocr_are_distinct():
    docs = [
        doc("건강보험료납부확인서", confidence=.55, detected=False, document_id=2,
            findings=[finding("UNKNOWN_DOCUMENT_TYPE")]),
        doc("건강보험자격확인서", document_id=3, findings=[finding("MISSING_REQUIRED_FIELD")]),
        doc("4대보험가입내역확인서", confidence=.6, document_id=4),
    ]
    items = project_reasons([low("건강보험료납부확인서"), low("건강보험자격확인서"), low("4대보험가입내역확인서")], docs)
    by_doc = {item["document_id"]: item for item in items}
    assert by_doc[2]["code"] == "UNKNOWN_DOCUMENT_TYPE" and by_doc[2]["title"] == "문서 종류 판별 불가"
    assert by_doc[3]["code"] == "MISSING_REQUIRED_FIELD" and by_doc[3]["category_label"] == "필수 정보 확인 필요"  # 확인필요 등급은 누락으로 단정하지 않음
    assert by_doc[4]["code"] == "LOW_OCR_CONFIDENCE" and by_doc[4]["category"] == "ocr"
    assert "60%" in by_doc[4]["message"] and "85%" in by_doc[4]["message"]
    # 우선순위: 필수 정보 누락 → 문서 종류 → OCR 신뢰도
    assert [item["document_id"] for item in items] == [3, 2, 4]


def test_priority_fail_conflict_then_review_and_stage2_order_kept():
    reasons = [
        low("주민등록초본"),
        {"stage": "stage1_document", "code": "DECLARED_DATE_UNCERTAIN", "message": "합성 발급일 불확실",
         "doc_type": "주민등록초본"},
        {"stage": "stage1_document", "code": "WRONG_DOCUMENT_TYPE", "message": "합성 종류 다름", "doc_type": "통장사본"},
        {"stage": "stage2_eligibility", "code": "INCOME_UNDETERMINED", "message": "합성 소득"},
        {"stage": "stage2_eligibility", "code": "WORK_CONTINUITY_UNDETERMINED", "message": "합성 근로"},
    ]
    items = project_reasons(reasons, [SCAN_DOC])
    assert [item["code"] for item in items] == [
        "WRONG_DOCUMENT_TYPE", "DECLARED_DATE_UNCERTAIN", "ADDRESS_HISTORY_INCOMPLETE",
        "INCOME_UNDETERMINED", "WORK_CONTINUITY_UNDETERMINED"]
    assert items[0]["severity"] == "FAIL" and items[1]["category"] == "conflict"
    assert [item.get("priority") for item in items] == [1, 2, 3, None, None]


def test_no_specific_reason_and_good_confidence_is_not_called_unreadable():
    [item] = project_reasons([low("통장사본")], [doc("통장사본", status="PASS")])
    assert item["code"] == "LOW_OCR_CONFIDENCE" and item["category"] == "other"
    assert item["title"] == "자동 적합 확정 안 됨" and "판독되지 않았" not in item["message"]
    assert item["origin"]["code"] == "LOW_OCR_CONFIDENCE"


def test_legacy_string_findings_do_not_break_projection():
    from demo.backend.review_reasons import annotate_findings
    legacy = doc("주민등록초본", findings=["FAKE 글자만 있는 과거 사유", finding("MISSING_REQUIRED_FIELD")])
    [item] = project_reasons([low("주민등록초본")], [legacy])
    assert item["code"] == "MISSING_REQUIRED_FIELD"
    views = annotate_findings(legacy["findings"], {})
    assert views[0] == {"message": "FAKE 글자만 있는 과거 사유", "category": "other",
                        "category_label": "담당자 확인 필요", "title": "FAKE 글자만 있는 과거 사유"}


def test_same_type_documents_each_keep_their_own_reason():
    # 근로확인서류 1·2처럼 같은 종류 칸이 여럿이면 엔진 사유(칸 없음)가 둘 다 같은 종류를 가리킨다.
    first = doc("4대보험가입내역확인서", document_id=11, findings=[finding("IDENTITY_UNCERTAIN")])
    second = doc("4대보험가입내역확인서", document_id=12, confidence=.3)
    items = project_reasons([low("4대보험가입내역확인서"), low("4대보험가입내역확인서")], [first, second])
    by_doc = {item["document_id"]: item for item in items}
    assert set(by_doc) == {11, 12}
    assert by_doc[11]["code"] == "IDENTITY_UNCERTAIN"
    assert by_doc[12]["code"] == "LOW_OCR_CONFIDENCE" and "30%" in by_doc[12]["message"]


def test_engine_capped_pass_document_is_not_dropped_when_reasons_outnumber_flagged_docs():
    flagged = doc("4대보험가입내역확인서", document_id=21, findings=[finding("MISSING_REQUIRED_FIELD")])
    capped = doc("4대보험가입내역확인서", document_id=22, status="PASS")
    items = project_reasons([low("4대보험가입내역확인서"), low("4대보험가입내역확인서")], [flagged, capped])
    assert {item["document_id"] for item in items} == {21, 22}
    assert next(i for i in items if i["document_id"] == 22)["title"] == "자동 적합 확정 안 됨"
    # 엔진 사유가 하나뿐이면 적합 서류에 사유를 지어 붙이지 않는다.
    assert {i["document_id"] for i in project_reasons([low("4대보험가입내역확인서")], [flagged, capped])} == {21}


def test_non_low_engine_reason_goes_to_the_document_that_stores_it():
    first = doc("4대보험가입내역확인서", document_id=31, status="PASS")
    second = doc("4대보험가입내역확인서", document_id=32, status="FAIL",
                 findings=[finding("DOCUMENT_ISSUED_TOO_EARLY", "FAIL")])
    reason = {"stage": "stage1_document", "code": "DOCUMENT_ISSUED_TOO_EARLY", "message": "합성 발급일 이전",
              "doc_type": "4대보험가입내역확인서"}
    [item] = project_reasons([reason], [first, second])
    assert item["document_id"] == 32 and item["category_label"] == "발급일 요건 확인" and item["severity"] == "FAIL"
    # 두 서류 모두 같은 코드면 각각 자기 서류로 남는다.
    both = [doc("4대보험가입내역확인서", document_id=d, status="FAIL", findings=[finding("IDENTITY_MISMATCH", "FAIL")])
            for d in (41, 42)]
    mismatch = {**reason, "code": "IDENTITY_MISMATCH"}
    assert [i["document_id"] for i in project_reasons([mismatch, mismatch], both)] == [41, 42]
    # 저장 사유가 없고 같은 종류가 여럿이면 서류를 추측하지 않는다.
    [unknown] = project_reasons([reason], [doc("4대보험가입내역확인서", document_id=51, status="PASS"),
                                           doc("4대보험가입내역확인서", document_id=52, status="PASS")])
    assert unknown.get("document_id") is None


def test_review_grade_wording_never_asserts_missing():
    past = doc("주민등록초본", findings=[finding("PAST_ADDRESS_OMISSION_SUSPECTED")])
    [item] = project_reasons([low("주민등록초본")], [past])
    assert item["category"] == "completeness" and "누락" not in item["category_label"]
    review = doc("주민등록초본", findings=[finding("MISSING_REQUIRED_FIELD")])
    [item] = project_reasons([low("주민등록초본")], [review])
    assert item["category_label"] == "필수 정보 확인 필요"
    confirmed = doc("주민등록초본", status="FAIL", findings=[finding("MISSING_ADDRESS_DATES", "FAIL")])
    [item] = project_reasons([low("주민등록초본")], [confirmed])
    assert item["category_label"] == "필수 정보 누락"  # 부적합으로 확정된 것만 "누락"


def test_stored_document_low_ocr_finding_is_kept_next_to_other_reasons():
    both = doc("주민등록초본", confidence=.4, findings=[finding("LOW_OCR_CONFIDENCE"), finding("DECLARED_DATE_UNCERTAIN")])
    codes = {item["code"] for item in project_reasons([low("주민등록초본")], [both])}
    assert codes == {"LOW_OCR_CONFIDENCE", "DECLARED_DATE_UNCERTAIN"}


def test_quality_reason_without_stored_finding_gets_no_invented_grade():
    reason = {"stage": "stage1_document", "code": "LOW_IMAGE_QUALITY", "message": "합성 화질", "doc_type": "통장사본"}
    [item] = project_reasons([reason], [doc("통장사본", status="PASS")])
    assert "severity" not in item


def test_explanation_keeps_stored_sentence_for_audit():
    from demo.backend.review_reasons import annotate_findings
    [view] = annotate_findings(SCAN_DOC["findings"], SCAN_DOC["extracted"])
    assert view["explanation"] == SCAN_COMPLETENESS_EXPLANATION
    assert view["stored_message"] == SCAN_DOC["findings"][0]["message"] == view["message"]


def test_duplicate_reasons_for_the_same_document_collapse():
    items = project_reasons([low("주민등록초본"), low("주민등록초본")], [SCAN_DOC])
    assert len(items) == 1


def _scan_resident(application_id):
    with models.get_session() as session:
        row = session.exec(select(models.Document).where(models.Document.application_id == application_id,
                                                         models.Document.slot_key == "resident_abstract")).one()
        ocr = deepcopy(row.ocr_json)
        ocr["fields"].update({"주소이력상태": "불확실", "주소이력불확실사유": "SCAN_UNVERIFIED",
                              "주소이력끝근거": "이하 여백 (3쪽)", "전입일": "불확실"})
        row.ocr_json = ocr
        row.stage1_status = "NEEDS_REVIEW"
        row.findings_json = [{**SCAN_DOC["findings"][0], "how_to_fix": "합성 안내",
                              "detail": "세부 사유: SCAN_UNVERIFIED"}]
        session.add(row)
        session.commit()
        return row.id


def test_officer_api_summary_matches_document_reason(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OFFICER_PASSWORD", "SYNTHETIC projection password")
    monkeypatch.setenv("OFFICER_SESSION_SECRET", "SYNTHETIC projection secret")
    application = ready(make_application(premium=1))
    did = _scan_resident(application.id)
    claim_synthetic_application(client, application.id)
    assert client.get(f"/api/applications/{application.id}/final-check").json()["can_submit"]
    assert client.post(f"/api/applications/{application.id}/submit").status_code == 200
    authenticate_officer(client, monkeypatch)
    with models.get_session() as session:
        review_before = deepcopy(session.exec(select(models.Review).where(
            models.Review.application_id == application.id)).one().model_dump())
        stored_doc = deepcopy(session.get(models.Document, did).model_dump())
    # 저장된 엔진 사유는 여전히 LOW_OCR_CONFIDENCE다(판정 규칙은 바꾸지 않았다).
    stored = [r for r in review_before["review_payload_json"]["reasons"] if r.get("doc_type") == "주민등록초본"]
    assert [r["code"] for r in stored] == ["LOW_OCR_CONFIDENCE"]
    assert review_before["final_status"] == "NEEDS_REVIEW"

    detail = client.get(f"/api/officer/applications/{application.id}").json()
    resident = [r for r in detail["ai"]["reasons"] if r.get("doc_type") == "주민등록초본"]
    assert [r["code"] for r in resident] == ["ADDRESS_HISTORY_INCOMPLETE"]
    assert resident[0]["title"] == SCAN_COMPLETENESS_TITLE and resident[0]["document_id"] == did
    assert all("자동으로 판독되지 않았" not in r["message"] for r in resident)
    assert any(r["code"] == "LOW_OCR_CONFIDENCE" for r in detail["ai"]["stored_reasons"])
    assert detail["ai"]["final_status"] == "NEEDS_REVIEW"  # 확인필요는 그대로 확인필요다.
    resident_doc = next(d for d in detail["documents"] if d["document_id"] == did)
    assert resident_doc["status"] == "NEEDS_REVIEW" and resident_doc["ocr_confidence"] == .95
    assert [f["code"] for f in resident_doc["findings"]] == ["ADDRESS_HISTORY_INCOMPLETE"]  # 기존 응답 그대로
    assert "category" not in resident_doc["findings"][0]
    assert resident_doc["finding_views"][0]["title"] == SCAN_COMPLETENESS_TITLE
    assert resident_doc["finding_views"][0]["message"] == SCAN_COMPLETENESS_DOC_MESSAGE  # 저장 문장 보존
    assert resident_doc["finding_views"][0]["explanation"] == SCAN_COMPLETENESS_EXPLANATION
    # 원본 파일 연결은 그대로다.
    assert resident_doc["file_url"] == f"/api/files/{did}"

    summary = client.get(f"/api/officer/applications/{application.id}/summary").json()
    text = json.dumps(summary, ensure_ascii=False)
    resident_points = [p for p in summary["check_points"] if p.get("slot_key") == "resident_abstract"]
    assert resident_points and all("신뢰도" not in p["title"] for p in resident_points)
    assert SCAN_COMPLETENESS_TITLE in text
    assert "SCAN_UNVERIFIED" not in summary["headline"] + summary["status_explanation"]

    with models.get_session() as session:
        assert session.exec(select(models.Review).where(
            models.Review.application_id == application.id)).one().model_dump() == review_before
        assert session.get(models.Document, did).model_dump() == stored_doc


SCAN_COMPLETENESS_DOC_MESSAGE = SCAN_DOC["findings"][0]["message"]
