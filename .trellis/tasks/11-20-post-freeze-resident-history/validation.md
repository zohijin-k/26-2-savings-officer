# Resident continuation verification

Date: 2026-11-21, Asia/Seoul. All 46 mandatory checks completed successfully with unchanged source hashes. This report was prepared for commit review. Additional own-render limitations are reported below.

## Scope and preserved evidence

- Frozen commit: `bdd8aade18cd0885ad7549011af5b21241c344b8`; frozen annotated tag object: `6bce0930f8a8482ad8e3ec1e9001aacad6999851`.
- Source changes: resident extraction, its demo conversion and the existing review reason description. OCR dispatch/models/weights, preprocessing, database and frontend source are unchanged.
- Real documents, H 150 labels/results and case 81 were not read or executed. No H data was used for tuning or regression. Historical holdout performance is not an independent validation result for this change.
- All measurements below use newly generated synthetic inputs. Keep external OCR disabled; no model installation or training occurred.

## Functional comparison

The six comparison conditions use the exact same authored inputs and fixed evaluation date before and after source edits. Counts are synthetic history entries, not real-document observations.

| Condition | Before count / backend | After count / backend |
|---|---|---|
| Ordinary two-page 8+2 | 10 / PASS | 10 / PASS |
| Nearby split continuation header | 8 / PASS | 10 / PASS |
| Insufficient header evidence | 8 / PASS | 8 / NEEDS_REVIEW |
| Split header with unread row | 8 / PASS | 8 / NEEDS_REVIEW |
| Split report-date value | 8 / PASS | 8 / NEEDS_REVIEW |
| Unrelated attachment | 8 / PASS | 8 / PASS |

Backend targeted transitions: PASS to NEEDS_REVIEW 3; all other changes 0. Direct engine targeted transitions: NEEDS_REVIEW to suitable 1; all other changes 0. The ordinary attachment already had a direct-engine missing-table warning before this change; its existing outcome is retained.

New tests additionally cover one-page and single-entry policies, one corroborated continuation row, header-label splitting, spacing boundaries, scale, character misreads, missing/damaged ordinals, independent date/identity/page FAIL, the existing page-confidence exception, detected empty tables through the direct engine, and exclusion of military/blank sections with and without table-like headers.

Date-value joining is deliberately omitted. Unread/fragmented/conflicting values require review; printed characters are never guessed.

## Baseline and final checks

| Check | Before source edits | Final source |
|---|---|---|
| New synthetic regression | Not applicable | 65 passed |
| Existing resident-related tests | Included in full baseline | 251 passed |
| Full engine pytest | 2755 passed, 3 skipped | 2793 passed, 3 skipped |
| Full backend pytest | 1861 passed | 1888 passed |
| Scenario modules | Existing reference: 18, zero failures | 18/18, twice sequentially; zero failures |
| Frontend tsc / oxlint / vite | All passed | All passed |
| Synthetic paired measurement | 410 pairs; own false PASS 0/235 | 410 pairs; zero execution errors; own false PASS 0/235 |
| Presentation G1 / G2 / INS4 | 25/25; 165/165; 25/25 | 25/25; 165/165; 25/25 |
| Validation G1 / G2 / INS4 | 25/25; 165/165; 25/25 | 25/25; 165/165; 25/25 |

Two intermediate post-edit paired runs were intentionally interrupted while adding synthetic other-section and malformed-date/ordinal tests. Their partial output is not a verification result. The final run uses the shared table-ending boundary, expanded unread-date evidence and new report destinations. No existing test failed and no expected value was changed.

## Final transition aggregation

All 410 input fingerprints and expected classes match before/after. Counts only; no individual document keys or values:

| Transition | Text-layer reference | Own |
|---|---|---|
| PASS to NEEDS_REVIEW | 0 | 0 |
| NEEDS_REVIEW to PASS | 0 | 0 |
| FAIL to PASS | 0 | 0 |
| PASS to FAIL | 0 | 0 |
| Other changes | 0 | 0 |

Own false acceptance remains 0/235. Reference false acceptance remains 20/235; this is an existing benchmark limitation, not a new success or a new error. Expected-valid review counts remain 115 for reference and 132 for own. The five original-condition resident examples were already review in both stages and remain five review; do not describe them as new PASS results. The separate positive one/two-page controlled tests retain PASS.

## Diagnostic compatibility and verified synthetic results

- Existing PDF tool: `/tmp/diagnose_resident_history_safe.py`. Existing numbered tool: `/tmp/diagnose_holdout_by_number.py`. Both original hashes are unchanged.
- The old `observe_bounds(lines)` rejects `allow_split`; a synthetic direct call reads ten entries while the legacy observer raises `TypeError`. Its invocation flag is set after return, so the exception leaves flags false. The old PDF self-test reproduces `SELF_TEST_FAILED` without any PDF argument; an unset shell PDF variable alone cannot explain that reproduction. The old numbered resolver's isolated self-test passes 42 cases but mocks diagnostic invocation.
- New PDF tool: `/tmp/diagnose_resident_history_safe_v2.py`; new numbered tool: `/tmp/diagnose_holdout_by_number_v2.py`. The numbered tool pins the new PDF script hash. No engine change was made to conceal a diagnostic error.
- New PDF self-test: 12/12; new numbered resolver self-test: 42/42. The PDF tests include intentional extractor failure and OCR failure; the former remains `EXTRACTION_ERROR`, invocation true, completion false, with a fixed error-type code.
- Guarded numbered-path integration: actual metadata/source entry points blocked, only a generated two-page byte stream and authored OCR used; committed entries 8+2=10, stage OK, extractor completion true.
- Additional actual own OCR render sample: frozen extractor 2/10, current extractor 2/10, both NEEDS_REVIEW; valid report-date word candidates were one per page. This sample is incomplete, not a recovery success or an extractor exception. The v2 command keeps expected count ten and returns nonzero with `SYNTHETIC_OWN_INCOMPLETE`. No model, source truth or expected count was altered to force success.

The last observation is an unchanged OCR/geometry limitation of that extra synthetic render. It does not establish what the real case contains or whether case 81 is recovered.

## Versioned diagnostic source hashes

- `diagnose_resident_history_safe_v2.py`: `b64a2d8203d1fe5f88728be90b3e2f845b1d228674f1839fde0bb67a49fab207`
- `diagnose_holdout_by_number_v2.py`: `3dde2744a348aad92d710f23b82b76641738a9544346cc62ba2a31077186b2ec`

## Remaining limits and user verification

Recovery is bounded to the supported column structure and observed header/row evidence. Large geometry changes, absent OCR evidence or ambiguous dates may remain reviewable or unresolvable. Synthetic 8+2 recovery does not establish recovery of real case 81.

From the repository root, verified synthetic preflight commands are:

```sh
JBAI_ALLOW_REAL_DOCS=false .venv/bin/python -B /tmp/diagnose_resident_history_safe_v2.py --self-test
JBAI_ALLOW_REAL_DOCS=false .venv/bin/python -B /tmp/diagnose_holdout_by_number_v2.py --self-test
```

Only the user may execute the real numbered command below. Codex has not executed it or opened its input:

```sh
JBAI_ALLOW_REAL_DOCS=false .venv/bin/python -B /tmp/diagnose_holdout_by_number_v2.py --number 81
```

The PDF alternative keeps `--pdf <local-absolute-PDF-path>`; keep that path local. Check process stage, extractor invocation/completion, committed per-page counts, total history, uncertainty and final status. A synthetically recovered count of ten is not evidence of real-case recovery.

## Proposed commit contents

One coherent change, message: `fix: recover multi-page resident history and flag incomplete tables`.

1. `engine_v2/extractors/resident_abstract.py`
2. `demo/backend/ocr/localocr.py`
3. `demo/backend/rules/doc_check.py`
4. `engine_v2/tests/test_resident_history_continuation.py`
5. `demo/backend/tests/test_resident_history_continuation.py`
6. `.trellis/spec/backend/document-form-contracts.md`
7. `.trellis/tasks/11-20-post-freeze-resident-history/task.json`
8. `.trellis/tasks/11-20-post-freeze-resident-history/prd.md`
9. `.trellis/tasks/11-20-post-freeze-resident-history/design.md`
10. `.trellis/tasks/11-20-post-freeze-resident-history/implement.md`
11. `.trellis/tasks/11-20-post-freeze-resident-history/implement.jsonl`
12. `.trellis/tasks/11-20-post-freeze-resident-history/check.jsonl`
13. `.trellis/tasks/11-20-post-freeze-resident-history/research/code-paths.md`
14. `.trellis/tasks/11-20-post-freeze-resident-history/validation.md`

File-by-file review and the unstaged patch security scan are complete; all five requested forbidden literals have zero matches. After the Trellis commit approval, add each listed file individually and repeat the five checks on the actual staged diff before committing. No amend or push.
