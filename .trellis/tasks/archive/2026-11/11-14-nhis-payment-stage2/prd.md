# NHIS_PAYMENT stage 2

## Goal
Improve NHIS_PAYMENT monthly extraction from demonstrated layout causes and explain upload-versus-reference behavior, while preserving NEEDS_REVIEW when period or amount evidence is uncertain.

## Authorized phase
Original structural implementation was approved on 2026-11-14, then stopped by its false-pass gate. User subsequently authorized staged investigation and holding the causal header-edge repair. Independent paging-guard implementation awaits separate approval. Commit requires separate approval. Work on `work/nhis-payment-stage2`.

## Background and evidence
- All own dumps use the government reader and pass its range-format check; the independent period evidence additionally reconciles out-of-range row observations. See `engine_v2/extractors/payment_period.py:86` and [research](research/findings.md).
- Normal supported text uploads consume text-layer words through LocalOcr; batch verdicts deliberately consume forced own OCR, with text reference used only for agreement. No text/own result merge occurs (`demo/backend/ocr/localocr.py:663`, `engine_v2/tools/batch_assess.py:715`). The user-reported 111 cases were not independently replayed or counted.
- Apple and text-reference dumps use legacy extraction. Smaller month boxes clip the government's recognition window (`engine_v2/extractors/nhis_payment_gov.py:31`); billing cause NONE is not a whole-document PASS.
- p001 has an extra non-month row before the sum that is assigned to the last month; global row checks then fail all column sums (`nhis_payment_gov.py:201`, `:252`). Its hidden label and numeric contents are unobservable. Two other independently reproduced mechanisms are component-band clipping (`:185`) and neighbor header-cluster fusion (`:121`).

## Requirements
- R1: Explain query-period outcomes using token splitting, punctuation, confidence, relative position and the independent row checks. Preserve uncertainty/conflicts rather than assuming zeros.
- R2: Document actual word sources and the normal-upload/forced-batch/reference distinction; cover it with synthetic end-to-end regressions.
- R3: Explain legacy monthly extraction and its safety limits. Do not copy Apple values or route incomplete government forms to a weaker reader.
- R4: Reproduce p001's extra-row mechanism using a known code-owned adjustment label and fix only positively identified bounded adjustment rows. Never ignore unknown extra rows or claim that masked source numerals are correct.
- R5: Separately reproduce and repair payment component-band clipping and uniquely resolvable cluster fusion. Missing/ambiguous heading or corridor evidence remains reviewable; defer fusion if safe uniqueness cannot be proved.
- R6: Use independently authored synthetic documents/word lists with relative source-like shapes before each fix; no copied private coordinate/value fixtures. Keep monthly averages/field meanings, eight-column arithmetic, paid total and confidence/review propagation.
- R7: Limit runtime changes to the payment reader; preserve OCR, shared layout helpers, other extractors, verdict rules, batch policy, reader selection, existing generator/truth/metrics and public field contracts.
- R8: Read only repository files and the explicitly supplied masked dump directory. Never commit dumps or create source-derived examples. Planning/research documents contain no copied masked values or source coordinates; summarize only necessary token/relative-layout shapes.

## Acceptance criteria
- AC1 (R1–R5): Research provides code anchors, confirmed mechanisms, synthetic probe results and explicit limits/deferred items for all four questions.
- AC2 (R4–R7): Cause-specific synthetic regressions fail before their repair and pass afterward; malformed/ambiguous variants retain review. Design and implementation plan specify the guards and rollback boundary.
- AC3: Any changed existing test expectation is reported by file/test/before/after/reason and separately approved before change.
- AC4: Run paired synthetic v2 measurement before/after, compare payment field accuracy and false passes; stop and report any false-pass increase. Private batch reassessment is user-operated with `batch_assess --ids`.
- AC5: Before any commit, present `git diff --stat main`, cause-by-cause changes and nonchanges, engine tests (reference 1535 + 3 skips), backend tests (1296), 18 scenarios (1885 + 0 failures), frontend lint/build and measurement comparison; await approval.

## Out of scope and deferred items
Private source documents and batch outputs, real-document reruns, source-value reconstruction, numeric OCR/model improvement, unidentified body-noise removal, period grammar expansion/conflict suppression, broad reader rerouting, unrelated extraction/rules, and automatic commits. Existing private stored rows receive no migration.

## Artifact and approval status
Research, design and ordered implementation plan are complete. Requirements have been consolidated against the final evidence; no user-owned scope decision remains unresolved. Implementation approved with exact settlement-label matching, strict average exclusion, unique header evidence, unchanged period handling, red/green regression evidence, expectation-change approval and false-pass stop gates.

## Paging follow-up requirements (user-directed)
- R9: Report isolated baseline/settlement/clipping/fusion/all-three verdicts on exactly s1_nhis_payment_pages_incomplete for native own and v2 text reference, with matching input/word fingerprints.
- R10: Report original findings and internal validation failures; distinguish an actual page-omission finding from incidental extraction review.
- R11: Propose independent payment paging: reliable missing pages => PAGES_INCOMPLETE FAIL; unreadable required/uncertain marker => NEEDS_REVIEW; do not infer new missing-page FAIL for markerless forms.
- R12: Retain noncausal repairs and hold the causal repair pending a proven independent guard. No new guard implementation before reviewed approval.
- R13: After implementation, full original-baseline v2 comparison (410 pairs) must show no increase in false passes or confirmed false rejections before commit approval is requested. Preserve exact old-expectation approval and all original privacy/scope constraints.

The current proposal and execution gates are in paging-design.md; stage results are in paging-investigation.md. The task is back in planning for this material safety-design change.

## Paging implementation authorization
User approved the independent payment-only guard for own/text, followed by header-edge recovery restoration. Other document paging wiring is audit-only. Report NEEDS_REVIEW increases and corrected pre-existing text-reference false passes. Old expectation changes require separate exact approval; no commit before full dual-rate gates.


## Latest accepted contract (supersedes earlier aggregation limitation)

Read-only inspection of both explicitly authorized repositories confirms one retained replacement file per explicit payment slot. Its physical page count is the received set: reliable, complete, consistent printed total greater than that count is PAGES_INCOMPLETE FAIL. No multi-file upload redesign or applicant checkout edit. Guidance changes are proposal-only. Confirmed period + required months + actually observed matching printed totals + source issue information are all required to exempt only paging review; 1/1 alone never supplies PASS. C2 remains held. User approved exactly19 of28 historical test adjustments; nine FAIL expectations stay unchanged. Add ten incomplete-table uncertain-marker route controls, period-denied and same-folder same-type multiplicity batch summaries. Preserve original corpus/truth/metrics and dual-rate stop gates. Final frozen candidate must pass all requested suites with explicitly held strict xfails and receive separate commit approval.
