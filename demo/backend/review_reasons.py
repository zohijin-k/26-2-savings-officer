"""담당자 화면용 확인 사유 투영 (11-27). 두배적금·youth 백엔드에 같은 파일로 둔다.

저장된 판정과 사유(`Review.review_payload_json`, `Document.findings_json`)는 바꾸지 않는다.
담당자 응답을 만들 때만 신청 단위 사유를 서류별 실제 검증 사유와 맞추고, 엔진이 기록한 원문은
`origin`(사유별)과 `stored_reasons`(신청 단위)로 함께 돌려준다.

왜 필요한가: `engine_adapter.to_engine_documents`는 저장 판정이 NEEDS_REVIEW인 서류의 신뢰도를 0.4로 낮춰
엔진 1단계에 넘긴다(자동 적합 방지, 기존 설계). 그래서 엔진은 확인필요 서류를 모두
`LOW_OCR_CONFIDENCE`("일부 항목이 자동으로 판독되지 않았습니다")로 기록한다. 판독 신뢰도 0.95인 스캔 초본
(`SCAN_UNVERIFIED`)이나 종류를 판별하지 못한 서류도 같은 문장이 되어 담당자를 오도한다.

규칙:
- 판정(PASS/FAIL/NEEDS_REVIEW)·코드·저장값은 그대로다. 새 PASS를 만들지 않고, 사유를 지우지 않는다.
- 엔진의 `LOW_OCR_CONFIDENCE`가 가리키는 서류에 구체적인 확인필요·부적합 사유가 있으면 그 사유로 보인다.
  서류 자신의 판독 신뢰도가 기준(엔진 OCR_CONFIDENCE_THRESHOLD) 미만이고 다른 사유가 없을 때만
  "OCR 판독 신뢰도 부족"으로 보인다. OCR 신뢰도와 서류 완결성은 다른 분류다.
- 신청 단위 서류 사유는 분류 우선순위(정보 충돌 → 필수 정보 누락 → 종류 → 완결성 → 화질 → OCR → 수동 검토)로
  정렬한다. 2단계(자격) 사유는 원래 순서대로 그 뒤에 둔다.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from .engine_adapter import engine_config

#: 분류 → (담당자 화면 이름, 우선순위; 작을수록 먼저 확인)
CATEGORIES: dict[str, tuple[str, int]] = {
    "conflict": ("정보 충돌", 10),
    "missing": ("필수 정보 누락", 20),
    "issue_date": ("발급일 요건 확인", 25),
    "doc_type": ("문서 종류 확인 필요", 30),
    "completeness": ("서류 완결성 확인 필요", 40),
    "quality": ("파일·화질 확인 필요", 50),
    "ocr": ("OCR 판독 신뢰도 부족", 60),
    "manual": ("담당자 수동 검토 대상", 70),
    "other": ("담당자 확인 필요", 80),
}
#: 확인필요 등급의 "필수 정보" 사유는 누락으로 단정하지 않는다(부적합으로 확정된 것만 "누락").
MISSING_REVIEW_LABEL = "필수 정보 확인 필요"

_CODE_CATEGORY: dict[str, str] = {
    **dict.fromkeys((
        "DECLARED_DATE_MISMATCH", "DECLARED_DATE_UNCERTAIN", "IDENTITY_MISMATCH",
        "INSURANCE_WORKPLACE_NAME_INCONSISTENT", "WORK_DOCUMENTS_CONFLICT", "AGE_IDENTITY_MISMATCH",
        "APPLICATION_HOUSEHOLD_SIZE_DIFFERS", "ACCOUNT_HOLDER_MISMATCH", "RECEIPT_AMOUNT_MISMATCH",
        "ADMIN_CONSENT_IDENTITY_MISMATCH", "PAGE_IMAGE_SHARED",
    ), "conflict"),
    **dict.fromkeys((
        "MISSING_REQUIRED_DOC", "MISSING_REQUIRED_FIELD", "MISSING_SIGNATURE", "ISSUE_DATE_MISSING",
        "MISSING_ADDRESS_DATES", "MISSING_ADDRESS_HISTORY", "MISSING_BILLING_MONTHS",
        "NHIS_HISTORY_PERIOD_MISSING", "DAILY_RECORDS_PARTIALLY_SELECTED", "ADMIN_CONSENT_NOT_GIVEN",
    ), "missing"),
    **dict.fromkeys(("DOCUMENT_ISSUED_TOO_EARLY", "DOCUMENT_ISSUED_AFTER_APPLICATION"), "issue_date"),
    **dict.fromkeys(("ADDRESS_HISTORY_INCOMPLETE", "PAST_ADDRESS_OMISSION_SUSPECTED",
                     "PAGES_INCOMPLETE", "PAGES_DUPLICATED"), "completeness"),
    **dict.fromkeys(("UNKNOWN_DOCUMENT_TYPE", "WRONG_DOCUMENT_TYPE"), "doc_type"),
    **dict.fromkeys((
        "LOW_IMAGE_QUALITY", "IMAGE_RESOLUTION_TOO_LOW", "SCREEN_CAPTURE_SUSPECTED", "UNREADABLE_FILE",
    ), "quality"),
    **dict.fromkeys((
        "LOW_OCR_CONFIDENCE", "REQUIRED_FIELD_UNREADABLE", "RESIDENT_APPLICANT_UNREADABLE",
        "RECEIPT_AMOUNT_UNREADABLE", "RECEIPT_OCR_UNAVAILABLE", "IDENTITY_UNCERTAIN", "PAGES_UNREADABLE",
        "NHIS_HISTORY_PERIOD_UNREADABLE", "PAYMENT_AMOUNT_COLUMN_UNCERTAIN",
        "PAYMENT_COMPONENT_HEADER_INCOMPLETE", "NHIS_PAYMENT_PAGING_UNCERTAIN", "PAYMENT_PAGING_UNCERTAIN",
        "ADMIN_CONSENT_IDENTITY_UNREADABLE", "ADMIN_CONSENT_IDENTITY_UNCERTAIN",
        "ADMIN_CONSENT_MARK_UNREADABLE", "ADMIN_CONSENT_MARK_UNCERTAIN", "ADMIN_CONSENT_SIGNATURE_UNREADABLE",
        "WORK_HISTORY_UNREADABLE",
    ), "ocr"),
    **dict.fromkeys((
        "RECEIPT_MANUAL_REVIEW", "MANUAL_DOCUMENT_REVIEW", "ACCOUNT_COPY_REVIEW", "VIEW_ONLY_DOCUMENT",
        "NHIS_SUBSCRIBER_IDENTITY_REVIEW", "NHIS_DEPENDENT_INSURED_PERSON", "HEALTH_INSURANCE_HOUSEHOLD_RECHECK",
    ), "manual"),
}

#: 사유 코드 → 담당자 화면 제목. 없는 코드는 저장된 제목이나 문장 첫머리를 쓴다.
TITLES: dict[str, str] = {
    "LOW_OCR_CONFIDENCE": "OCR 판독 신뢰도 부족",
    "UNKNOWN_DOCUMENT_TYPE": "문서 종류 판별 불가",
    "WRONG_DOCUMENT_TYPE": "요구한 서류와 종류가 다름",
    "MISSING_REQUIRED_FIELD": "필수 항목 누락",
    "REQUIRED_FIELD_UNREADABLE": "필수 항목 판독 안 됨",
    "DECLARED_DATE_MISMATCH": "입력한 발급일과 서류 발급일이 다름",
    "DECLARED_DATE_UNCERTAIN": "입력한 발급일과 판독 발급일이 다름(판독 불확실)",
    "IDENTITY_MISMATCH": "서류 명의가 신청자와 다름",
    "IDENTITY_UNCERTAIN": "서류 명의 판독 불확실",
    "LOW_IMAGE_QUALITY": "화질이 낮음",
    "RECEIPT_MANUAL_REVIEW": "결제영수증 담당자 원본 확인 대상",
    "MANUAL_DOCUMENT_REVIEW": "담당자 원본 확인 대상",
    "ACCOUNT_COPY_REVIEW": "통장 사본 담당자 확인 대상",
}

#: 주소이력불확실사유(두배적금·youth `ocr/localocr.py`) → 담당자 문구. 단정하지 않는다("누락"이라 쓰지 않음).
ADDRESS_UNCERTAIN_LABELS: dict[str, str] = {
    "NUMBER_GAP": "주소이력 순번이 중간에 이어지지 않음",
    "NUMBER_UNREADABLE": "주소이력 순번을 읽지 못함",
    "EMPTY_PAGE": "이력 줄을 하나도 읽지 못한 쪽이 있음",
    "TABLE_NOT_FOUND": "다음 쪽의 이력 표를 찾지 못함",
    "ROWS_UNREADABLE": "다음 쪽 이력 줄을 다 읽지 못함",
    "NUMBER_START": "주소이력 순번이 1로 시작하지 않음",
    "UNREAD_ROWS": "표를 찾지 못한 쪽에 이력 번호가 보임",
    "END_UNCONFIRMED": "마지막 이력 아래 끝 표시(이하 여백·다음 구역)를 확인하지 못함",
    "SCAN_UNVERIFIED": "스캔 초본은 주소이력 끝부분까지 제출됐는지 자동으로 확정하지 않음",
}
_ADDRESS_READ_GAPS = frozenset({
    "NUMBER_GAP", "NUMBER_UNREADABLE", "EMPTY_PAGE", "TABLE_NOT_FOUND", "ROWS_UNREADABLE",
    "NUMBER_START", "UNREAD_ROWS",
})
SCAN_COMPLETENESS_TITLE = "스캔 주민등록초본의 주소이력 완전성 확인 필요"
SCAN_COMPLETENESS_EXPLANATION = "주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다."

_SEVERITY_RANK = {"FAIL": 0, "NEEDS_REVIEW": 1}
_REVIEW_STATES = ("NEEDS_REVIEW", "FAIL")


def address_uncertain_codes(extracted: Mapping[str, Any] | None) -> list[str]:
    raw = str((extracted or {}).get("주소이력불확실사유") or "")
    return [code.strip() for code in raw.split(",") if code.strip()]


def describe(code: str, extracted: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """코드 하나의 분류·제목·설명. 주소이력 사유는 서류의 `주소이력불확실사유`로 나눈다."""
    category = _CODE_CATEGORY.get(code, "other")
    out: dict[str, Any] = {"category": category, "category_label": CATEGORIES[category][0]}
    if code in TITLES:
        out["title"] = TITLES[code]
    if code == "ADDRESS_HISTORY_INCOMPLETE":
        sub = address_uncertain_codes(extracted)
        out["details"] = [ADDRESS_UNCERTAIN_LABELS.get(item, "그 밖의 사유") for item in dict.fromkeys(sub)]
        if _ADDRESS_READ_GAPS & set(sub):
            out["title"] = "주소이력 일부 판독 불완전"
            out["explanation"] = "주소이력 순번이나 줄 일부를 자동으로 읽지 못해, 빠진 이력이 있는지 담당자 확인이 필요합니다."
        elif "END_UNCONFIRMED" in sub:
            out["title"] = "주소이력 끝 표시 미확인"
            out["explanation"] = ("마지막 이력 아래 끝 표시(이하 여백·다음 구역)를 확인하지 못해, "
                                  "주소이력의 끝부분이 모두 제출됐는지 담당자 확인이 필요합니다.")
        elif "SCAN_UNVERIFIED" in sub:
            out["title"] = SCAN_COMPLETENESS_TITLE
            out["explanation"] = SCAN_COMPLETENESS_EXPLANATION
        else:
            out["title"] = "주소이력 완전성 확인 필요"
    return out


def annotate_findings(findings: Iterable[Mapping[str, Any]], extracted: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """서류 사유에 분류·제목·설명을 붙인다. 원래 키(code·message·severity·detail …)는 그대로 둔다.

    코드 없이 문장만 저장된 과거 사유도 빠뜨리지 않는다(문장을 message로 둔 한 건).
    """
    return [_with_info(finding if isinstance(finding, Mapping) else {"message": str(finding)}, extracted)
            for finding in findings]


def _doc_type_of(doc: Mapping[str, Any]) -> str | None:
    return doc.get("detected_doc_type") or doc.get("expected_doc_type")


def _first_sentence(text: str) -> str:
    head = (text or "").replace("'", "").strip().split(". ")[0].rstrip(".")
    return head[:40] if head else "담당자 확인 필요"


def _confidence(doc: Mapping[str, Any]) -> float | None:
    value = doc.get("ocr_confidence")
    return float(value) if isinstance(value, (int, float)) else None


def _graded(item: dict[str, Any]) -> dict[str, Any]:
    """확인필요(또는 등급 미상) "필수 정보" 사유는 "누락" 대신 "확인 필요"로 보인다."""
    if item.get("category") == "missing" and item.get("severity") != "FAIL":
        item["category_label"] = MISSING_REVIEW_LABEL
    return item


def _with_info(reason: Mapping[str, Any], extracted: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """저장된 사유에 분류를 붙인다. 이 모듈이 제목을 정하지 않은 코드는 저장된 제목을 유지한다.

    설명(explanation)이 저장 문장을 대신해 보일 때는 저장 문장을 stored_message로 함께 남긴다(감사용).
    """
    item = dict(reason)
    info = describe(str(item.get("code") or ""), extracted)
    stored_title = item.get("title")
    item.update(info)
    if "title" not in info:
        item["title"] = stored_title or _first_sentence(str(item.get("message") or ""))
    if info.get("explanation") and item.get("message") and item["message"] != info["explanation"]:
        item.setdefault("stored_message", item["message"])
    return _graded(item)


def _specific_findings(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """서류에 저장된 확인필요·부적합 사유(코드가 있는 것). 서류 자체의 LOW_OCR_CONFIDENCE도 실제 사유다."""
    return [finding for finding in doc.get("findings") or []
            if isinstance(finding, Mapping) and isinstance(finding.get("code"), str)
            and finding.get("severity", "FAIL") in _REVIEW_STATES]


def _fallback(reason: Mapping[str, Any], doc: Mapping[str, Any]) -> dict[str, Any]:
    """서류에 구체 사유가 없을 때: 실제 신뢰도가 기준 미만이면 OCR 신뢰도, 아니면 '자동 적합 확정 안 됨'."""
    origin = {"code": reason.get("code"), "message": reason.get("message")}
    item = {**dict(reason), "severity": "NEEDS_REVIEW", "slot_key": doc.get("slot_key"),
            "document_id": doc.get("document_id"), "stored_message": reason.get("message")}
    confidence = _confidence(doc)
    if confidence is not None and confidence < engine_config.OCR_CONFIDENCE_THRESHOLD:
        item.update(describe("LOW_OCR_CONFIDENCE"))
        item["explanation"] = (f"자동 판독 신뢰도 {round(confidence * 100)}%로 기준"
                               f"({round(engine_config.OCR_CONFIDENCE_THRESHOLD * 100)}%)보다 낮습니다. "
                               "원본에서 값을 확인해 주세요.")
    else:
        # 엔진이 이 서류를 자동 적합으로 확정하지 않았지만 서류에 저장된 구체 사유가 없다. 판독 실패로 단정하지 않는다.
        item.update({"category": "other", "category_label": CATEGORIES["other"][0], "title": "자동 적합 확정 안 됨",
                     "explanation": "자동 판정이 이 서류를 적합으로 확정하지 않았습니다. 원본에서 확인해 주세요.",
                     "origin": origin})
    item["message"] = item["explanation"]
    return item


def _document_items(reason: Mapping[str, Any], doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """엔진 LOW_OCR_CONFIDENCE 한 건이 가리키는 서류 하나 → 그 서류의 실제 사유들(없으면 대체 한 건)."""
    origin = {"code": reason.get("code"), "message": reason.get("message")}
    out = []
    for finding in _specific_findings(doc):
        item = _with_info(finding, doc.get("extracted"))
        item.update({"stage": reason.get("stage"), "severity": finding.get("severity", "FAIL"),
                     "message": item.get("explanation") or finding.get("message") or "",
                     "doc_type": reason.get("doc_type"), "slot_key": doc.get("slot_key"),
                     "document_id": doc.get("document_id"), "origin": origin})
        for key in ("how_to_fix", "link", "detail"):
            item.pop(key, None)
        out.append(_graded(item))
    return out or [_fallback(reason, doc)]


def _replacement(reason: Mapping[str, Any], documents: list[Mapping[str, Any]], expected: int) -> list[dict[str, Any]]:
    """엔진 LOW_OCR_CONFIDENCE → 같은 종류 서류들의 실제 사유.

    엔진 사유에는 칸(slot)이 없어 종류로만 찾는다. 같은 종류 서류가 여럿(예: 근로확인서류 1·2)이면
    확인필요·부적합 서류마다 자기 사유를 낸다. 그런 서류 수가 엔진 사유 수(expected)보다 적으면
    저장 판정이 적합인데 엔진이 낮춘 서류(예: 발급일 근거 없음)도 대체 사유로 함께 보인다. 사유를 버리지 않는다.
    """
    matches = [doc for doc in documents if reason.get("doc_type") and _doc_type_of(doc) == reason.get("doc_type")]
    if not matches:
        return [_fallback(reason, {})]
    flagged = [doc for doc in matches if doc.get("status") in _REVIEW_STATES]
    targets = flagged if len(flagged) >= expected else matches
    return [item for doc in targets for item in _document_items(reason, doc)]


#: 엔진 1단계(engine/stage1_document_check.py)가 확인필요로만 내는 코드.
_ENGINE_REVIEW_CODES = frozenset({"LOW_OCR_CONFIDENCE", "DECLARED_DATE_UNCERTAIN"})
#: 화질 등급에 따라 부적합·확인필요가 갈리는 코드. 저장 사유가 없으면 등급을 지어내지 않는다.
_ENGINE_GRADED_CODES = frozenset({"LOW_IMAGE_QUALITY"})


def _owner(reason: Mapping[str, Any], documents: list[Mapping[str, Any]], used: set[Any]) -> Mapping[str, Any] | None:
    """엔진 사유(LOW_OCR 외)의 서류: 같은 코드를 저장한 같은 종류 서류 중 아직 배정되지 않은 것.

    그런 서류가 없고 같은 종류 서류가 하나뿐이면 그 서류. 여럿이면 추측하지 않는다(None).
    """
    same_type = [d for d in documents if reason.get("doc_type") and _doc_type_of(d) == reason.get("doc_type")]
    holders = [d for d in same_type if any(isinstance(f, Mapping) and f.get("code") == reason.get("code")
                                           for f in d.get("findings") or [])]
    for doc in holders:
        if (reason.get("code"), doc.get("document_id")) not in used:
            return doc
    if holders:
        return holders[0]
    return same_type[0] if len(same_type) == 1 else None


def _severity(reason: Mapping[str, Any], doc: Mapping[str, Any] | None) -> str | None:
    code = reason.get("code")
    stored = next((f.get("severity", "FAIL") for f in (doc or {}).get("findings") or []
                   if isinstance(f, Mapping) and f.get("code") == code), None)
    if stored:
        return str(stored)
    if reason.get("stage") != "stage1_document" or code in _ENGINE_GRADED_CODES:
        return None  # 데모 자체 1단계 사유·화질 등급은 저장 사유 없이 지어내지 않는다.
    return "NEEDS_REVIEW" if code in _ENGINE_REVIEW_CODES else "FAIL"


def project_reasons(reasons: Iterable[Mapping[str, Any]], documents: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """신청 단위 사유 → 담당자 화면용 목록 (응답 시점, 저장하지 않음)."""
    reasons = [reason for reason in reasons if isinstance(reason, Mapping)]
    low_count: dict[Any, int] = {}
    for reason in reasons:
        if reason.get("code") == "LOW_OCR_CONFIDENCE" and str(reason.get("stage") or "").startswith("stage1"):
            low_count[reason.get("doc_type")] = low_count.get(reason.get("doc_type"), 0) + 1
    document_reasons: list[dict[str, Any]] = []
    other_reasons: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    used: set[tuple[Any, Any]] = set()
    for reason in reasons:
        if not str(reason.get("stage") or "").startswith("stage1"):
            other_reasons.append(_with_info(reason) if reason.get("code") in _CODE_CATEGORY else dict(reason))
            continue
        if reason.get("code") == "LOW_OCR_CONFIDENCE":
            items = _replacement(reason, documents, low_count.get(reason.get("doc_type"), 1))
        else:
            doc = _owner(reason, documents, used)
            item = _with_info(reason, doc.get("extracted") if doc else None)
            severity = _severity(reason, doc)
            if severity:
                item["severity"] = severity
            if doc:
                item.setdefault("slot_key", doc.get("slot_key"))
                item.setdefault("document_id", doc.get("document_id"))
                used.add((reason.get("code"), doc.get("document_id")))
            items = [_graded(item)]
        for item in items:
            key = ((item.get("code"), item.get("document_id")) if item.get("document_id") is not None
                   else (item.get("code"), item.get("doc_type"), item.get("message")))
            if key in seen:
                continue
            seen.add(key)
            document_reasons.append(item)
    document_reasons.sort(key=lambda item: (_SEVERITY_RANK.get(str(item.get("severity")), 2),
                                            CATEGORIES.get(str(item.get("category")), CATEGORIES["other"])[1]))
    for rank, item in enumerate(document_reasons):
        item["priority"] = rank + 1
    return document_reasons + other_reasons
