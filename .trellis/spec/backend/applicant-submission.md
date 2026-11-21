# Applicant submission boundary

## Scope
The savings applicant UI submits from step three. `GET /final-check` remains the preparation API and `POST /submit` recomputes blockers from current stored inputs. Internal engine checks, document findings, Review statuses, scoring and officer projections retain their original contracts.

## Public document projection
`api.common.REUPLOAD_CODES` is the single ten-code allowlist: DOCUMENT_ISSUED_TOO_EARLY, DOCUMENT_ISSUED_AFTER_APPLICATION, IDENTITY_MISMATCH, IMAGE_RESOLUTION_TOO_LOW, LOW_IMAGE_QUALITY, PAGES_INCOMPLETE, UNREADABLE_FILE, MISSING_ADDRESS_DATES, MISSING_BILLING_MONTHS, WRONG_DOCUMENT_TYPE. Select only findings with severity FAIL; historical omitted severity keeps its existing FAIL default, but a missing/unknown code is never inferred from a message or stage1_status. NEEDS_REVIEW of the same code is hidden.

Applicant document.status is UPLOADED or REUPLOAD_REQUIRED, independent of the stored stage1_status. Public findings contain only allowlisted failures and public keys; confidence, internal details and other FAIL/NEEDS_REVIEW/INFO findings are absent. Identity masking must inspect the complete original findings before filtering. Never promote a hidden outcome to PASS or mutate stored evidence.

Identity/read/status responses do not include eligibility blockers. Self-check answers are stored and evaluated as before, but public results include only completed and total_items. Applicant warnings and supplement guidance must not reveal hidden judgments. When all supplement targets are hidden, return no applicant supplement object, preserving the original stored deadline and officer response; generic program-wide policy notices remain. Diagnostic CLIs retain raw reason/document/work/income outputs; only applicant_reason and applicant blockers follow this policy.

## Submission checks
Keep authentication/ownership and already-submitted protections. Check required written-form values, a valid required savings email, saving purpose and other required step-two inputs, completed self-check answers, conditional written-form requirements, required consents/signature or selected paper consent upload, all required upload slots, selected work category and allowlisted document failures. Preserve other programs' required subsidy-item checks. Internal income, age, work and self-check eligibility results never block applicant submission. There is no submit-anyway override.

Both preparation and direct submission use the same blocker function. A previously clear preparation response cannot authorize submission after an upload/input change. The frontend flushes pending saves, invalidates stale readiness and disables submission while loading, uploading, saving or submitting.

## Verification
Use synthetic documents and temporary databases only. Cover each allowlist code in FAIL and NEEDS_REVIEW, hidden/unknown/legacy/mixed findings, identity masking, immutable original data, direct-API required-field/consent/document/work checks, readiness-to-submit changes, and real submission of hidden failures with unchanged Review/officer outcomes. Record every changed existing expectation with file, test, before/after and reason; delete no tests.

## Unsupported auto uploads

### 1. Scope / trigger

`api.documents.upload_document` rejects unsupported automatic document classification
at the API boundary. This is an input restriction only; explicit-slot extraction,
OCR, document checks, submission policy and historical reviews remain unchanged.

### 2. Signatures

`POST /api/applications/{application_id}/documents` accepts multipart `file`,
`slot_key: str = Form(AUTO_SLOT)` and `declared_issue_date: str | None = Form(None)`.
The retained default is rejected; callers must supply an explicit upload slot.

### 3. Contracts

After the existing authentication middleware, reject `not slot_key` or exact
`slot_key == "auto"` before application/checklist loading, file reads, permanent
storage, OCR, assessment, document replacement or review recalculation. Return
HTTP 400 with the standard `{"detail": str}` body and this guidance:

`자동 서류 분류 업로드는 현재 지원하지 않습니다. 서류 종류에 맞는 업로드 항목을 선택해 다시 제출해 주세요.`

Keep the existing local PP-OCRv5/ONNX path and explicit-slot `assess_upload` call.
Starlette owns multipart temporary files and closes them on rejected requests,
including files rolled to disk. Temporary parsing is not permanent storage.

### 4. Validation & error matrix

| Input | Result |
|---|---|
| `auto`, omitted Form field, empty Form field, multipart `None` encoded empty | 400 unsupported-auto guidance |
| Query `slot_key` with no/empty Form slot | Same 400; Query cannot supply Form data |
| Whitespace, literal `null`/`None`, `AUTO`, padded ` auto `, unknown slot | Existing 400 invalid-slot error; no trimming/case folding |
| Explicit current checklist slot with `upload=True` | Existing format/date/assessment behavior |
| Missing required file | Existing framework validation error |

### 5. Good / base / bad cases

Good: the applicant explicitly uploads a PDF to `work_proof`. Base: image and text
PDFs use their existing ordinary-slot paths. Bad: assuming an omitted slot is a
valid default or enabling the private merged helper from another public route.

### 6. Tests required

`test_auto_upload_rejection.py` covers image/text PDFs, identity mismatch, workplace
conflict, implicit-auto forms and other invalid slots. Compare every DB table,
permanent file hashes, stored FAIL/NEEDS_REVIEW and officer PASS queue; assert zero
OCR, assessment, merged processing or review calls and closed multipart handles.
The synthetic historical-risk test demonstrates that stored unassigned documents
can coexist with PASS and remain excluded by a fresh review. This restriction
performs no migration or historical reassessment; remediation requires separate work.

### 7. Wrong vs correct

Wrong: disable the frontend button or reject only after writing/assessing a file.
Correct: reject at the input boundary and prove permanent state remains unchanged.
Wrong: claim existing auto documents are repaired. Correct: report their remaining
risk separately without changing stored data or engine rules.
