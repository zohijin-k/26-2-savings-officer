# Independent payment paging guard — implementation approved

## Goal and confirmed cause

The original own NEEDS_REVIEW was caused by table extraction, not missing-page detection. Header-edge recovery removes that incidental blocker. The original reference already passes the defective case. Native ablation isolates header-edge recovery as the causal repair; settlement and neighbor fusion individually do not change its verdict. Both paths can read the synthetic printed 1/2 with the existing independent marker helper (own confidence approximately .999, reference 1.0). The missing piece is evidence propagation and an independent assessment gate.

## Separation of responsibilities

1. Add a payment-only paging collector, provisionally `engine_v2/extractors/payment_paging.py`. It consumes original page/word observations and an explicit form-policy result, not monthly fields, sums, structure_complete or overall document confidence. Reuse existing marker parsing where applicable without altering its shared behavior. A payment-specific extension may cover positively supported upper-left/upper-right folio cells, bounded above the body/title metadata. Never read a body fraction as a folio or narrow a crossing word into guessed text.
2. Call it for classified NHIS_PAYMENT in LocalOcr independently of whether government or legacy table extraction succeeds. Preserve original physical page count, selected form-page indices and additional-attachment indices separately. A dissimilar attachment cannot satisfy a missing form folio. Text, own and v2 reference use the same collector; neither source receives a bypass.
3. Retain structured evidence in a versioned payment-only field, provisionally `납부쪽표기자료`. Proposed keys: `version`, `policy`, `status`, `uploaded_page_count`, `form_page_indices`, `markers`, `expected_total`, `marker_confidence`. No new eligibility/amount field is added. Missing/malformed historical evidence cannot establish a new FAIL; fresh readers explicitly emit uncertainty.
4. Merge the independent payment findings at the common `check_document` boundary, so body/identity/low-confidence early returns cannot hide a proven page omission. Scope to classified payment and preserve encryption/type/file-quality handling. Then run the existing quality/guidance finalizer. Do not change legacy engine rules or other document extractors.

## Policy and evidence states

`policy`: REQUIRED / NOT_REQUIRED / UNRESOLVED. Use positive form-version/layout evidence independent of table extraction success. A current reader's generic government/legacy choice, filename, amount-map presence or absence of a marker alone is not proof of a markerless template.

`status`: READABLE / UNREADABLE / ABSENT / AMBIGUOUS / NOT_REQUIRED. Require one entire valid marker per applicable page, valid integer bounds, consistent totals, independent per-marker confidence (initial threshold .85, matching the existing helper) and complete token accounting. Multiple candidates, conflicting totals, partial digits, low confidence or unreadable relevant pages remain uncertainty. Preserve whole source words and original geometry.

A fresh document with a completely missing required marker can be indistinguishable from a genuinely markerless document unless independent form-policy evidence exists. Do not claim that an OCR-only algorithm resolves that ambiguity. The conservative default is UNRESOLVED + NEEDS_REVIEW, not a new reupload FAIL. Positively identified markerless variants remain NOT_REQUIRED and retain existing nonpaging assessment. No public evidence currently establishes a complete markerless-template catalog; implement only supported positive policies, and retain review for unresolved cases.

## Verdict contract

| Evidence | Outcome |
| --- | --- |
| Reliable consistent total exceeds the received applicable form pages | PAGES_INCOMPLETE FAIL, independently of table/confidence success |
| Reliable complete page set | Continue all existing checks; do not force PASS |
| Required marker missing/unreadable/low-confidence/conflicting | NHIS_PAYMENT_PAGING_UNCERTAIN NEEDS_REVIEW |
| Policy unresolved and no conclusive marker | Same review-only finding; no inferred missing-page FAIL |
| Positively identified markerless variant | No new paging finding |
| Historical evidence absent or malformed | Never infer a confirmed omission; preserve compatibility or explicit review without new FAIL |

Use a payment-only review code with manual-inspection guidance. Do not reuse a code in `ESSENTIAL_FIELD_UNREADABLE_CODES` if that would turn a separately acceptable quality score into LOW_IMAGE_QUALITY FAIL solely because paging is uncertain. Preserve existing independently proven quality/date/type/identity failures. Register the code in safe verification vocabularies as required. Ensure upload/list/final-check/income fact handling preserves paging review and cannot consume uncertain payment evidence as confirmed income.

## Minimal expected changes

- New payment paging module and new synthetic tests.
- Narrow NHIS_PAYMENT collection/attachment-scope branch in `demo/backend/ocr/localocr.py`.
- Narrow payment-only finding merge in `demo/backend/rules/doc_check.py`, plus safe code registration if needed.
- Restore header-edge recovery only after the new paging tests pass and its defect becomes PAGES_INCOMPLETE FAIL in both own and reference paths.
- Preserve settlement separation, neighbor fusion, payment period handling, benchmark corpus/truth/metrics and all unrelated extractors/rules.

## Synthetic-first implementation order

1. Add authored word/PDF regressions for complete 1/1, received 1/2, multiple complete folios, missing/blurred/low-confidence/split/duplicate/conflicting markers, body fractions and boundary-crossing tokens. Vary table readable/unreadable state independently. Test own and text/reference paths.
2. Cover markerless and unresolved-policy variants explicitly; neither can create a new PAGES_INCOMPLETE FAIL without positive count evidence. Test normal, low-resolution and independently defective-quality cases so the review code adds no false quality rejection. Preserve additional attachment scope and actual upload persistence/final reassessment behavior.
3. Implement collection and independent verdict merge after approval. Keep header-edge recovery held until both-path missing-page regression passes; then restore it and repeat the scoped ablation/control. Verify settlement amounts still never enter monthly averages.
4. Do not alter an old assertion opportunistically. Existing markerless synthetic uploads may now change PASS to NEEDS_REVIEW under the unresolved-policy rule; report exact affected file/test/old/new/reason and obtain approval before any expectation edit. Known examples requiring explicit review are `demo/backend/tests/test_p2_payment_uploads.py::test_payment_upload_matches_identity_and_persists_all_corrections` and `::test_payment_text_layer_upload_keeps_same_financial_field_contract`, whose current sources omit a folio and expect PASS. This is a predicted impact, not a claim that all affected cases are enumerated or permission to modify their fixtures. Do not add folios to the frozen benchmark or weaken its negatives to obtain PASS.
5. Run the unchanged full n=5, seed=20261113 v2 corpus: 410 pairs / 820 stages. Compare with the completed original baseline, not the halted 29-pair run. Require identical case/input/source fingerprints. Compare both false acceptance and confirmed false rejection by stage, document, group, condition and each case. A newly passing negative, an increased false-pass slice, a newly false-rejected valid case or an increased false-rejection slice stops work. Quality/content negatives retain their authored populations.
6. Repeat all four regression groups on final source and show main-relative diff plus cause dispositions. Request commit approval only after both rate gates and all required checks pass. No private case measurement, commit or push is authorized here.

## Current approval status

User approved guard implementation for both own and text paths. Add a read-only cross-document wiring audit, report review-count increases and recovered pre-existing reference false passes, preserve old-expectation approval, and require full original-baseline 410-pair false-pass/false-rejection nonincrease before requesting commit approval. No old assertion change is authorized yet.


## Superseding approved refinement (2026-11-14)

User rejects all 26 folio input edits. Implement payment-only fallback in both routes only with READABLE nonconflicting query interval, every requested month, actually observed printed totals matching monthly sums, and received issue information read from source. Page markers never establish PASS; complete 1/1 with incomplete table remains REVIEW. Conflicting totals retain REVIEW. Search only isolated upper/lower margin tokens outside table; exclude date/period/money shapes. Report accepted grammars and shape-only masked-dump adoption.

Submission-set constraint: API replaces the same slot and does not retain/assign split files as one payment submission. Batch/verify/v2 also lack an authoritative complete submission set. Per explicit condition 3, do NOT introduce a new count-based PAGES_INCOMPLETE FAIL under this structure. A reliable apparent excess stays nonwaivable REVIEW with an explanation. Do not redesign upload persistence or silently count a directory as a submission. This means condition 5-a's FAIL cannot be delivered in this structure; report its safe REVIEW fallback. Preserve existing unrelated FAILs. Test split-file observations as non-FAIL.

C2 header-edge recovery is HELD again. Retain C1 exact-label settlement and C3 unique neighbor split. New regressions precede runtime edits. Existing test/fixture/assertion files remain unchanged; report any failure and expectation impact before considering changes. Batch statistics add value-free per-route adoption, total buckets and file-local count mismatches, with backward-compatible historical records. Final complete 410-pair original-baseline comparison must not increase false pass/reject. Run all four requested regression groups; any existing failure is reported without test edits. No commit without approval; provide staged secret/private-data hygiene evidence.


## Latest conditional decision — supersedes no-FAIL aggregation fallback

Both codebases retain one replacement file per explicit slot. The current file is therefore the complete slot submission. Restore independent PAGES_INCOMPLETE FAIL only for complete/reliable/consistent total greater than physical file pages; compare selected form pages separately for fallback and attachment safety. Keep nine prior FAIL expectations unchanged. The read-only audit and guidance-only proposal are in paging-single-file-upload-audit.md. Never use a folder's file multiplicity as an upload-set count. User-approved19 test changes, ten new incomplete controls, connected whole-row date/money exclusion, and source-financial snapshot binding are final. Final measurement/check root is engine_v2/data/stage2_paging_final_20261115. Earlier interrupted review-policy/prehardened runs are excluded.
