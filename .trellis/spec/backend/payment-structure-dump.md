# Payment structure dump contracts

## 1. Scope / trigger

Apply to structured `layout_dump --out`, its local helper and new synthetic tests. This is stage-1 value-masked evidence collection for NHIS_PAYMENT. Preserve legacy layout helpers/console behavior, operating OCR/classification/extraction/assessment/verdict code and every existing test file. Real-document inputs are never used in development or regression validation.

## 2. Signatures

`PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.layout_dump FAKE-input.pdf --out FAKE-output.json`

Examples are fictitious. --out implies all three fixed engines (`text_layer`, `own`, `applevision`) and rejects a single-engine override. There is no unmasked option, automatic discovery or source-derived output name. Require an existing output parent.

## 3. Contracts

- Reuse batch guarded inspection/in-memory explicit engine calls and checked atomic writing plus `verify_cases._private_location`. Validate actual output and temporary siblings outside the processing guard. Inside checkout requires ignored AND untracked; reject aliases/hardlinks/source overwrites. Do not add ignore rules or bypass flags.
- Force both local OCR engines on the same 300 DPI in-memory PDF rendering. Preserve per-page partial text coverage without changing batch's full-document reference eligibility. Preserve adapter word order, confidence and unrounded pixel bounds; retain production page numbering. Existing RRN stars are not restored.
- Closed projection: fixed schema/masking version and engine names, page/word indices and sizes, boxes/width/height/confidence, masked word text and fixed diagnostics. No paths/names/stems, source metadata/raw text, extracted fields/values, full results/evidence, exception messages, value hashes or dynamic object serialization. Validate numeric geometry before projection.
- Literal word exceptions come ONLY from existing `nhis_payment` CARE/HEALTH/OUTSIDE_HEALTH/MONTH_LABELS/TABLE_LABELS/TABLE_LABEL_FRAGMENTS and `nhis_payment_gov` COMPONENTS/HEADERS/GROUPS module constants. Their current union is 28 strings. Exact original whole-word membership only; no normalized permission, broad privacy labels, function-body literals, fixture additions or automatic substring fragments. The complete approved list is in task design. Diagnostics also project names through this vocabulary.
- Otherwise digits→9, Hangul/Jamo→가, Latin→A. Preserve whitespace/punctuation/symbols; mask other alphabets rather than retaining values. Never change operating word content/boxes or pass masked words to extraction.
- Diagnostics run original payment extraction under scoped observers and project only recognized allowlisted heading names, observed component-cluster count and matched-heading count against nine expected, month count, scope and safe validation names. Distinguish NOT_RUN/null from actual zero. Reuse SAFE_VALIDATIONS; unknown names map to a fixed marker.
- Reuse production LocalOcr conversion/payment-period collection and billing checker with canonical payment requirements. A diagnostic is not a full upload assessment. Derive cause enums from structured existing branches, not finding messages; keep dates/months/amounts/periods and finding detail in memory. A readable period can still fall through to review when the monthly amount map is missing, unreadable or lacks a required key; project that separately from period uncertainty. Table-row absence is separate from billing-check causes. Restore all observers and guards on failure.
- During processing suppress Python/native/log output, deny writes/DB/subprocess/network and disable bytecode; save only the final projection after leaving the guard. No original rasters/temp OCR files, caches, model downloads, remote/fallback engines or raw run logs. Console is fixed status/counts only, never paths/argument echoes/tracebacks.

## 4. Validation and error matrix

| Condition | Result |
| --- | --- |
| Complete report without actual processing errors | Exit 0 |
| No text layer for a page | NOT_APPLICABLE/TEXT_LAYER_ABSENT; not an OCR error |
| Optional Apple unavailable | SKIPPED/ENGINE_UNAVAILABLE |
| Actual OCR/word/diagnostic failure | Fixed error state, exit 1; no dynamic details |
| Arguments/location/input/output/serialization contract failure | Exit 2; old output preserved |
| Interrupt | Exit 130; no partial replacement |

## 5. Good, base and bad cases

Good: all three provider arrays retain order/boxes while name/amount/number sentinels disappear and nine-header/month/validation/billing diagnostics contain only fixed labels/counts/codes. Base: legacy `mask` and `group_lines` tests keep their expectations. Bad: preserving a label substring inside a value-bearing word, inventing a missing-month verdict from failed table validation, exporting a field dictionary or printing an output path.

## 6. Required tests

New test modules only. Assert exact 28-string constant-derived vocabulary; exact membership/character substitutions (including Unicode); full serialization plus console contains no declared synthetic document-value sentinels; merged/split/line words retain original order/geometry. Cover complete/partial/no-text/multipage inputs, recognized/missing headers and months, all production billing cause branches and malformed evidence, safe validation vocabularies, optional capability versus engine failure, location/alias/hardlink/atomic failures and guard/wrapper restoration. Final gate includes full engine/backend/18-scenario/frontend checks, unchanged protected-source evidence, actual synthetic dump with diagnostics and git diff --stat main; wait for explicit commit approval.

## 7. Wrong versus correct

Wrong: use the old substring/region masking or interpret UNDETERMINED period evidence as confirmed table loss. Correct: exact whole-word constant membership and an independent structured billing-cause projection with explicit diagnostic scope. Wrong: regroup words before saving. Correct: retain provider order/boxes and observe parser grouping separately through scoped original-helper calls.
