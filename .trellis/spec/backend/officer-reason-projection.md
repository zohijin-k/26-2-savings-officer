# Officer reason projection (11-27)

Shared file: `demo/backend/review_reasons.py` is byte-identical in `26-2-savings-officer` and `26-2-youth`.
Change it in both repositories together.

## Why
`engine_adapter.to_engine_documents` lowers the engine confidence of every document whose stored
stage1 is NEEDS_REVIEW to 0.4 (intended: such documents can never become an engine PASS). The engine
therefore records `LOW_OCR_CONFIDENCE` ("일부 항목이 자동으로 판독되지 않았습니다") for all of them. A scanned
주민등록초본 read at confidence 0.95 and held by `SCAN_ABSTRACT_REVIEW_GUARD` (`주소이력불확실사유=SCAN_UNVERIFIED`)
or an unknown-type upload was shown to officers as a low-OCR problem.

## Contract
- Response-time only. `Review.review_payload_json`, `Document.findings_json`, statuses, scores, the engine
  and the adapter downgrade are unchanged. No PASS is created and no reason is dropped.
- `review_detail().ai.reasons = project_reasons(stored reasons, document views)`:
  - A stage1 `LOW_OCR_CONFIDENCE` reason carries no slot, so it is matched by type (detected, else expected).
    Every matched FAIL/NEEDS_REVIEW document contributes its own stored FAIL/NEEDS_REVIEW findings (a stored
    document-level `LOW_OCR_CONFIDENCE` is a real reason and is kept). A matched document without such findings
    contributes one fallback: `LOW_OCR_CONFIDENCE`/category `ocr` only when its own `ocr_confidence` is below
    `engine.config.OCR_CONFIDENCE_THRESHOLD`, otherwise `other` / "자동 적합 확정 안 됨" (never "판독되지 않았습니다").
    Stored-PASS documents of that type are included only when the engine emitted more `LOW_OCR_CONFIDENCE`
    reasons for the type than there are flagged documents (e.g. a PASS capped for a missing issue date).
    Replacements keep `origin` (`{code, message}` of the engine reason) and `stored_message`.
  - Other stage1 reasons are attached to the same-type document that stores the same code (each such document
    once); with no holder and a single same-type document, to that document; otherwise no `document_id` (no guessing).
  - Each stage1 item gets `category`, `category_label`, `title`, `severity` (stored finding severity, else engine
    stage1 semantics: `LOW_OCR_CONFIDENCE`/`DECLARED_DATE_UNCERTAIN` review, quality-graded `LOW_IMAGE_QUALITY`
    none, other engine codes FAIL; demo-only `stage1_documents` reasons none), `document_id`, `slot_key`, `priority`.
  - Order: stage1 items by severity (FAIL first) then category priority
    정보 충돌 < 필수 정보 누락 < 발급일 요건 < 문서 종류 < 서류 완결성 < 파일·화질 < OCR 판독 신뢰도 < 담당자 수동 검토 < 기타;
    then stage2 items in stored order. Duplicate (code, document) items collapse.
  - Wording: "필수 정보 누락" only for FAIL; review-grade or ungraded items in that category read "필수 정보 확인 필요".
    `PAST_ADDRESS_OMISSION_SUSPECTED`, `PAGES_INCOMPLETE`, `PAGES_DUPLICATED` are 서류 완결성; issue-date codes are 발급일 요건.
- `ai.stored_reasons` returns the stored engine list unchanged (savings: with `readable_reason` titles) for audit.
- `ADDRESS_HISTORY_INCOMPLETE` titles come from `주소이력불확실사유`: read gaps → "주소이력 일부 판독 불완전";
  `END_UNCONFIRMED` → "주소이력 끝 표시 미확인"; only `SCAN_UNVERIFIED` →
  "스캔 주민등록초본의 주소이력 완전성 확인 필요" with explanation
  "주소이력의 끝부분이 모두 제출됐는지 자동으로 확정할 수 없어 담당자 확인이 필요합니다." Never state "누락".
  OCR confidence and document completeness are separate categories; high OCR confidence never hides a
  completeness review.
- Document views keep `findings` exactly as before (savings: `readable_reason` titles; youth: stored values)
  and add `finding_views` with `category`/`category_label`/`title`/`explanation`/`details`. String-only
  legacy findings appear in `finding_views` as `{message}`.
- Savings AI summary: evidence labels use the projected title for codes absent from `CODE_LABELS`;
  `SUMMARY_VERSION` 5.
- Applicant responses are unaffected (they never include these reasons).

## Tests
`demo/backend/tests/test_officer_reason_projection.py` (both repositories): scan completeness vs OCR,
high-confidence completeness, sub-reason titles, unknown type / missing field / true low OCR,
priority and stage2 order, no-finding fallback, dedupe, and a stored-review → officer API case that
fails on the pre-change main (`LOW_OCR_CONFIDENCE` shown for the scanned 초본) with stored rows unchanged.
