# Paging safety investigation — analysis only

## Stage 1: independent repair ablation

Exactly s1_nhis_payment_pages_incomplete was regenerated through the unchanged v2 corpus with seed 20261113. Its input fingerprint matches the completed original baseline. Each condition ran actual native own OCR and the v2 text-word reference through the same image/upload pipeline. Per-stage word fingerprints are identical across all five variants. Baseline verdicts and field metrics match the completed 410-pair baseline.

| Enabled repair | Own | Text reference |
| --- | --- | --- |
| None (original source) | NEEDS_REVIEW | PASS |
| Settlement only | NEEDS_REVIEW | PASS |
| Header-edge clipping only | PASS | PASS |
| Neighbor fusion only | NEEDS_REVIEW | PASS |
| All three | PASS | PASS |

The causal repair for this case is header-edge clipping. The reference path already falsely passes before all repairs. These are scoped experiments, not a new complete v2 run. Variant code and synthetic raster remain ignored; numeric/code-only evidence is in paging-ablation.json. No private document or dump is used in these experiments.

Stage 1 was reported before examining stage 2 reason codes.

## Stage 2: original assessment reasons

| Variant/path | Status | Findings | Internal failed validations |
| --- | --- | --- | --- |
| Original own | NEEDS_REVIEW | LOW_OCR_CONFIDENCE (review), MISSING_BILLING_MONTHS (review) | payment_component_headers, payment_columns, paid_total_matches |
| Original reference | PASS | None | None |
| Clipping-only own | PASS | None | None |

Original own confidence is .4 and the monthly map is absent. Original reference confidence is .95 with the map present. All paths receive one physical page; neither emits payment paging fields. No PAGES_INCOMPLETE finding exists in the original own result.

`LocalOcr._read` collects generic independent markers only when content classification fails (`localocr.py:770`). Classified payment instead uses `_from_supported_form` / `_from_nhis`, which emits period evidence but no paging evidence (`:517`, `:398`). `doc_check` only consumes the generic independent marker field in the specific tiny/unreadable-resolution early branch (`doc_check.py:483`); resident paging has its own separate path. The ordinary classified payment path therefore does not compare printed total against received pages. Government `payment_single_page` merely checks physical input length, not the printed count.

A separate observation with the existing independent marker helper reads synthetic 1/2 in both actual own and reference words, with confidence approximately .999 and 1.0 respectively; numeric-only evidence is in paging-marker-probe.json. The case is therefore a missing connection of readable evidence, not an inability to recognize its marker. Stage 2 was reported before guard design/holding work.

## Stage 3: proposal

The next-step proposal is not yet implemented; see paging-design.md for architecture, evidence states, independent FAIL/review behavior, markerless ambiguity, predicted existing-test impact and the complete synthetic validation gates. This proposal was reported before holding the causal repair.

## Stage 4: causal repair held

Removed only the header-edge recovery branch from the operating government reader. Settlement separation and neighbor fusion remain wired. The held-control rerun uses native own and the original text reference with the same input fingerprint: own NEEDS_REVIEW, reference PASS. Numeric/code-only evidence is in paging-held-control.json. The reference false PASS remains an acknowledged defect for the proposed independent paging guard; no new rule has been implemented yet.

Focused retained coverage: 57 passed / 10 deselected (new header-edge recovery cases and their upload/conflict parameters). Those deferred tests were not changed or deleted; the previous full four-group results predate this hold and are not represented as a fresh full verification of the held working tree. No old expectation was edited.

## Stage 5: required after implementation approval

After the independent guard is approved/implemented and the held repair is safely restored, rerun all 410 v2 pairs against the completed original baseline. Require no increased false acceptance or confirmed false rejection, no newly passing negative and no newly false-rejected valid case. Preserve source/truth/metric/input fingerprints and separate normal/stress/quality/content populations. Run all four regression groups again. Commit approval is requested only after every gate passes; no commit is authorized now.
