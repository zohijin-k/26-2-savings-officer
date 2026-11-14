# Pre-change quality and essential-field assessment

## Evidence inspected

Only repository code and authored synthetic fixtures were inspected. A diagnostic Python invocation constructed the five sparse-address variants and printed their finding codes and grades. No real-document input was opened. The initial worktree was clean on main.

## Pre-change measurement and ordering

1. `demo/backend/ocr/file_evidence.py`, `objective_image_quality` at line 45, measures the uploaded source. Raw images below a 1,000px short edge receive a score below the .6 cutoff. Dominant bitmap PDF pages below 150dpi also receive a below-cutoff score. Text-layer pages and certified excluded attachments follow existing source rules.
2. `_check_document` in `demo/backend/rules/doc_check.py` first returns UNREADABLE_FILE at line 460, then checks the separate severe-resolution evidence at line 463. `resolution_defect` requires short edge below 600 AND long edge below 800 plus its existing applicable unreadability evidence. These conditions remain protected.
3. Unknown/wrong-type results return early around lines 487-518. Daily, business and insurance form checks also return early, including REQUIRED_FIELD_UNREADABLE results around lines 535-598.
4. `engine/stage1_document_check.py`, `check_single_document` at line 25, emits LOW_IMAGE_QUALITY before date/confidence checks. The demo invokes it around `doc_check.py` line 616.
5. Demo essential checks include required checklist fields around line 673, payment-period checks around line 703, NHIS period evidence around line 707, resident applicant identity around line 737 and four-insurance identity around line 764. NHIS uncertainty can downgrade collected FAIL findings near line 905.
6. Public `check_document`, line 915, receives all early returns, deletes any existing LOW_IMAGE_QUALITY finding, and unconditionally recreates it with `_finding`'s default FAIL when quality is below cutoff. This is the decisive current override at lines 931-939.
7. `upload_assessment.assess_upload` adds consent and receipt observations after that wrapper. Receipt OCR-unavailable handling around lines 93-106 reconstructs the finding list and preserves only certain FAIL findings. A quality-grade change must account for this final postprocessing.
8. At submission, `api/review.py` line 524 calls the original pipeline through `engine_adapter.to_engine_documents` and `run_pipeline`. The adapter forwards the raw quality score. `engine.stage1_document_check.run_stage1` treats LOW_IMAGE_QUALITY as hard FAIL at lines 113-119. Upload-only changes would therefore leave a second quality FAIL in application review.

## Existing essential-field evidence

- REQUIRED_FIELD_UNREADABLE identifies required checklist fields, missing NHIS identity/date and incomplete applicable forms.
- RESIDENT_APPLICANT_UNREADABLE identifies resident applicant name/birth unreadability.
- RECEIPT_AMOUNT_UNREADABLE identifies the required receipt amount. RECEIPT_OCR_UNAVAILABLE is added after check_document when no receipt recognition is available.
- NHIS_HISTORY_PERIOD_UNREADABLE identifies unreadable required history coverage. Payment `MISSING_BILLING_MONTHS` has two meanings depending on its existing branch and grade. The review branch represents unreadable required period/month evidence. Its confirmed FAIL branch represents an observed content defect.
- ADMIN_CONSENT_IDENTITY_UNREADABLE, ADMIN_CONSENT_MARK_UNREADABLE and ADMIN_CONSENT_SIGNATURE_UNREADABLE represent applicable required consent observations.
- Generic LOW_OCR_CONFIDENCE, IDENTITY_UNCERTAIN, PAGES_UNREADABLE and NHIS_SUBSCRIBER_IDENTITY_REVIEW each have causes beyond missing essential fields. They cannot alone prove the conjunction. Ambiguous codes require the original branch's field-readability evidence.
- `MISSING_REQUIRED_FIELD` and independently proven date/month omissions already carry their own FAIL. Reading a value and finding it unacceptable is distinct from a missing read.

## Screen and API consequences

`demo/README.md` lines 3 and 126 document the current officer-only frontend. Applicant interaction remains represented by retained APIs, without a runnable applicant page in this checkout.

`api/common.py` line 193 projects applicant findings. When any FAIL exists, same-document NEEDS_REVIEW findings are hidden. With review-only quality, the quality warning becomes visible together with existing review guidance. `api/review.py` line 116 blocks documents only for stage1_status FAIL. A review-only quality warning therefore removes this document's reupload blocker, subject to other existing blockers.

The officer projection at `api/officer.py` line 654 retains complete findings. `StatusBadge.tsx` maps NEEDS_REVIEW to 확인필요 and FAIL to 부적합. `pages/officer/document-groups.ts` groups every non-PASS document into 확인 필요 서류. Both old and new quality outcomes use that group, while the detail badge and reason text change. `ReviewDetail.tsx` renders stored message and how_to_fix directly.

## Focused diagnostic findings

All five synthetic sparse-address variants currently carry RESIDENT_APPLICANT_UNREADABLE in addition to quality and general reading warnings. The blank-date variant also has MISSING_ADDRESS_DATES FAIL. Under the proposed conjunction all five retain LOW_IMAGE_QUALITY FAIL, as their applicant identity remains unreadable. This includes existing case-shaped CLI and upload regressions. Lowering every quality failure globally would incorrectly change these tests.

## Relevant specifications

- `.trellis/spec/backend/failure-filtering.md`
- `.trellis/spec/backend/document-form-contracts.md`
- `.trellis/spec/backend/documentai-measurement.md`
- `.trellis/spec/frontend/officer-documents.md`
