# Full-change review

## Runtime boundary

Only `engine_v2/extractors/nhis_payment_gov.py` changes runtime behavior. OCR/providers, shared layout helpers, preprocessing, adapters, batch policy, other extractors and rules remain byte-identical to the starting tracked source. All existing tests and fixture providers remain byte-identical. The `recognizes` function is AST-identical. `payment_period.py` is unchanged. No public field, migration or API is added.

## Guard review

| Change | Evidence and conservative boundary |
| --- | --- |
| Adjustment | One complete word must equal the fixed constant exactly, with a unique label, certain bounded row, required values and no crossing/unaccounted row words. Unknown/duplicate/partial/misplaced/uncertain rows retain failure. |
| Average exclusion | Only the local arithmetic `observed` list receives adjustment components. The twelve-row `values` list is never extended with them; monthly serialization and `_average` consume only `values`. Tests use different nonzero billed/paid adjustments and verify unchanged monthly maps/averages, and missing monthly health cells remain missing. |
| Clipped headings | Recovery includes all observations whose centers are below the group edge; added observations require certain confidence and the complete expected header set. Missing/extra/conflicting labels fail; the original successful path is retained. |
| Fused headings | Only one fused pair is considered. Whole observations are assigned in a comparison view, all nine labels must match in order, body corridors must independently validate the result, and exactly one assignment may survive. No source word is cropped or omitted. Empty/ambiguous optional corridors do not permit recovery. |
| Period | New balanced-table cases prove that complete arithmetic after each repair still cannot override an out-of-range positive; final assessment remains NEEDS_REVIEW. |
| Routes | Authored text PDF uploads bypass own for sufficient-text pages. Forced batch consumes own words, assesses its conflict and retains its text reference separately. Legacy monthly output without a billing finding still retains arithmetic review. |

The existing `_header_columns` text validation was extracted into `_headers_match` without changing its grammar. This allows proposed whole-fragment partitions to reuse the same exact-label check. Full existing regression suites verify compatibility; no test expectation adjustment is authorized or needed so far.

## Synthetic source refinement

The initial fused-header positive fixture left optional body columns empty. Under the approved conservative corridor rule, that geometry cannot independently support a split. The new fixture was corrected to print all eight columns, matching the necessary relative evidence in the investigated shape. Its empty-optional version remains a dedicated negative test. This did not change any existing fixture, benchmark source/truth or expected verdict. A pristine-source rerun with the corrected new fixture confirms the positive regression fails before the repair.

## Verification status

New focused coverage: 67 passed (49 engine, 18 backend). Pristine source plus the first 63 finalized tests: 22 expected positive regression failures / 41 passing guards. Repairs turn those 63 green; four additional missing-month/complete-table conflict guards also pass. Full engine final: 1,584 passed / 3 existing skips, compared with the independently rerun pristine 1,535 / 3. Full backend: 1,314 passed. All 18 scenarios: 1,885 counted checks, zero failures. Paired v2 after measurement was stopped at 29 pairs after one new own negative-case PASS. See measurement-stop.md. The change is not ready for commit despite passing regressions. Frontend lint/build passed, with the existing chunk-size advisory.

An earlier baseline measurement and concurrent validation attempts were interrupted by disk exhaustion from taAPI-key-prefixowned pytest temporary artifacts. They are excluded from acceptance evidence. Only taAPI-key-prefixcreated generated directories were removed, no private data; retries use pytest's `tmp_path_retention_policy=none` and contained TMPDIR. Failed numeric checkpoint/log files remain ignored for audit. Final acceptance requires completed before/after reports with matching inputs.
