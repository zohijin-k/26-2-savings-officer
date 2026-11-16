# Own adapter diagnostics

## 1. Scope / trigger

Applies to `engine_v2.tools.own_adapter_diag` and its diagnostic-only evidence helper/tests. The tool observes page-local OCR/extractor boundaries; it does not repair OCR, change confidence, alter production extraction/decisions or infer private-document causes. Existing tools and tests remain unchanged.

## 2. Signatures

```text
python -B -m engine_v2.tools.own_adapter_diag --root PATH --out NEW_PATH
  [--ids ROOT_RELATIVE_PDF_LIST] [--limit POSITIVE_INT]
  [--engines own applevision] [--fields TYPE:ASCII_FIELD_CODE ...]
extract_with_form(page, words, engine) -> (result, raw_fields, LEGACY|GOVERNMENT|OTHER)
diagnose(page, reference_words, observed_words, kind, key, reference_raw,
         observed_raw, observed_kind, engine, reference_form=None, observed_form=None) -> fixed diagnostic code
```

All `batch_assess.FIELDS` pairs have fixed public ASCII codes. Defaults are NHIS_PAYMENT MEMBERSHIP/BILLING_MONTH/ISSUE_DATE. Reject unknown/duplicate engine or field selections and existing output directories. Reuse existing location/inventory safety without modifying the shared selector. The diagnostic-only list accepts immediate folder IDs and root-relative PDF paths, ignores blank/comment lines, skips invalid/missing lines numerically and deduplicates overlapping selected files. Names never determine type; nonmatching classified documents are skipped/countable rather than forced into the requested type.

## 3. Contracts

- Reuse `ocr_baseline_runtime.reference_page`, `quality`, clean `variant_image`, `recognize`, and the exact existing `extract` path. Actual payment dispatch is observed through scoped wrappers around `nhis_payment.extract` and `nhis_payment_gov.extract`; always delegate and restore.
- Preserve reference/OCR words and confidence. Baseline NFKC/masking is symmetric. Counterfactuals affect copies only and replay the same original runtime extraction. A successful replay never replaces the measured result.
- LINE_MERGED requires the observed box itself to uniquely overlap every split component's reference cell. A successful replay alone cannot justify transplanting text from another column/row. Visible literal components in composite boxes exclude confident absence/character-error attribution when alignment remains ambiguous.
- Public files: run.json, results.jsonl, summary.json, summary.txt, summary_brief.txt. Closed schemas allow only reviewed codes, positive document ordinals, nonnegative page/counter integers, finite rates and null. Never output input IDs/paths, text/values, coordinates, hashes, exception details or arbitrary keys, including stderr/native/argparse paths.
- Execute dependency imports, PDF/OCR/extraction and evidence analysis inside existing quiet/read-only/no-network guards. Validate projections before persistent append and validate summaries before text/JSON output.
- Keep reference eligibility, completed match opportunities and causal diagnosed counts separate. Unsupported attribution must not remove a completed mismatch. Empty/unavailable/error OCR is reported separately with undefined comparison flags. Zero-denominator rates are null.
- Keep both raw typed equality and existing normalized semantic equality. Normalized success takes precedence as OK.
- Causal priority is fixed: OK, ROUTE_MISMATCH, LABEL_NOT_FOUND, LABEL_SPACED, LABEL_SPLIT, VALUE_NOT_FOUND, VALUE_OTHER_LINE, LINE_MERGED, ORDER, NORMALIZE, PATTERN_MISMATCH, OCR_CHAR, OTHER. Unknown or ambiguous evidence stays explicit.

## 4. Validation / error matrix

| Condition | Contract |
| --- | --- |
| Bad args/selection/location/output/schema | Fixed code only; exit 2; no overwrite |
| Encrypted/no text/short/broken/unclassified page | Separate exclusion; no fabricated agreement |
| Missing reference | REFERENCE_MISSING, eligible/count 0 |
| Present reference, unsupported causal evidence | REFERENCE_UNATTRIBUTABLE; completed agreement can still be measured |
| Engine unavailable/empty OCR | Separate availability state; no manufactured zero/one match |
| Reference/render/OCR/extraction/guard failure | Fixed execution status; causal count 0; exit 1 when execution-error records exist |
| Interrupt | Fixed INTERRUPTED; exit 130 |
| Expected exclusions only | Exit 0 means processing completed, not document PASS |

REFERENCE_ERROR, RENDER_ERROR and PROCESSING_ERROR are execution populations, not additions to the thirteen-cause vocabulary. A per-field evidence failure must not drop other fields or completed comparison opportunities.

TYPE_NOT_REQUESTED is a counted-zero page state for a confidently classified unrequested kind. `skipped_documents` counts attempted PDFs with no requested-kind page; `classified_unrequested_documents` separately counts the all-pages-confidently-unrequested subset. Input/quality/unknown exclusions retain their own populations. Folder expansion never changes classification, duplicates never trigger a second PDF attempt, and invalid/missing line counts are per skipped line.

## 5. Good / base / bad cases

- Base: existing normalized comparison matches: OK, even if raw exact equality differs.
- Good: a literal anchor splits across adjacent boxes in its supported region; report a split only after the measured field failed, with ambiguity checks.
- Good: an unlabeled closing date has no required issue-date label; do not borrow an unrelated print-date label elsewhere.
- Bad: join arbitrary columns, collapse duplicate observations, invent a value or use a copied counterfactual as measured extraction.
- Bad: call a missing engine or absent government membership 0% recognition accuracy.

## 6. Tests required

Use independently authored token/PDF fixtures. Cover all thirteen causes and precedence collisions, actual baseline dispatch/replay/restoration, exact/normalized distinction, label-free membership, component months, unlabeled dates, ambiguous/duplicate/neighbor evidence, Unicode/DPI/rotation limits, input rename/selection/limit/errors and explicit denominators. Privacy sentinels must remain absent from every artifact and Python/native/error output; swallowed write/DB/network attempts must remain blocked. Assert original words/confidence and existing Apple callable inputs remain unchanged.

Run new focused tests and the full engine_v2 suite in a tracked-source isolation with synthetic samples. Under the approved stage-2-1 boundary, paths inside engine_v2/tools/, engine_v2/tests/, engine_v2/docs/ and .trellis/ require engine_v2 only. Any changed path outside that set adds backend, all 18 scenario modules and frontend verification. Report main...HEAD and working-tree paths to justify this scope. Existing ignored document/upload/DB trees must not be inspected. Compare full engine pass growth with the collected new-test count; preserve every existing assertion.

## 7. Wrong versus correct

Wrong: require a literal 가입구분 label; search a serialized month list on the page; assign OCR_CHAR to a combined month/amount token merely because whole-token grammar fails.

Correct: inspect the actual reader's reference-supported branch, decompose derived months, prove unique spatial candidates or a bounded replay, and retain OTHER/REFERENCE_UNATTRIBUTABLE when evidence is insufficient. Report synthetic/private form differences rather than claiming a private cause.

## 8. Dispatch distributions and cross-tabulation

`summary.json.routes.distributions` reports completed extraction paths for `text_layer` and each selected OCR engine by LEGACY/GOVERNMENT/OTHER. `routes.cross` reports each engine's reference-form by observed-form page counts. `summary.txt` exposes the same fixed codes and integers as ROUTE and ROUTE_CROSS lines, including zero cells. Deduplicate by document/page for each engine across all selected fields. Reference paths include classified-unrequested and classification-failed pages after successful reference extraction. Observed paths count successful extraction after OCR, even when reference fields are absent or evidence diagnosis fails. Unattempted and failed paths have null form codes and do not enter dispatch counts. OTHER is a completed dispatch through another reader.

The CLI passes both observed form codes into diagnose. A present-reference normalized match remains OK. On a mismatch, a different observed dispatch is ROUTE_MISMATCH before classification/label/value/evidence diagnoses. Missing reference and execution/availability failures keep their explicit status. A route mismatch records the dispatch difference without identifying the failed classifier predicate. Test page deduplication, zero cells, incomplete paths, OTHER paths, missing references, OK/route/classification/label precedence and closed numeric schemas.

## 9. Routing predicate diagnostics

`own_adapter_route_diag.inspect_extraction(page, words, engine, extract)` delegates the primary extraction once, observes the exact payment/recognizes inputs and return, then projects conditions and bins. Preserve the three-item extraction return and all original results.jsonl/run.json fields. Scope wrappers to primary extraction, restore them on every exit, and exclude field-evidence replays from observations. Analyze prospective prepared copies for completed OTHER paths with PAYMENT_DISPATCH_CALLED X. Unknown/empty/unavailable OCR receives explicit status counts and contributes zero measured O/X patterns.

The ordered condition vocabulary, half-open distribution boundaries and CLI precedence are specified in the same task's stage-2-1 design. New summary.route_conditions contains only fixed condition_order, bin_definitions and groups keyed by reference_form/engine. Each group carries page/status counts, O/X condition counts, binned distributions and pattern/actual-form page counts. Deduplicate per document/page/engine across fields. Validate closed key sets, enum vocabularies, finite fixed boundaries, integer count types and partition sums before persistence. Keep raw geometry, medians, counts inside a box, input strings and page identities out of these new aggregates.

Compare decomposed government gates with the original recognizes return. PREDICATE_DIVERGENCE and CONDITION_ERROR preserve measured field results and appear in condition status counts. Either diagnostic status makes the run exit 1 while existing execution counters keep their original meaning. Commit document observations only after the read-only guard exits successfully, so a rejected side effect cannot leave orphan diagnostic records.

`summary_brief.txt` includes population/availability counts, full ROUTE/ROUTE_CROSS, CONDITION_ORDER, BIN definitions, CONDITION O/X counts, nonzero DISTRIBUTION and CONDITION_PATTERN rows, FIELD_POPULATION denominators and nonzero FIELD code/status rows. Its fixed code/number vocabulary makes a pasted brief self-contained. Full summary.txt retains existing lines and appends condition output.

Static --help exits 0 before filesystem/OCR access. Distinguish ROOT_NOT_DIR, OUT_EXISTS, OUT_INSIDE_ROOT, ROOT_INSIDE_OUT, IDS_NOT_FOUND, IDS_INVALID and SYMLINK_REJECTED. Preserve LOCATION_REJECTED/OUTPUT_ERROR and INTERRUPTED. ARGUMENT_ERROR is reserved for argument parsing/validation. UNEXPECTED_ERROR includes only a reviewed built-in exception_type, mapping custom exceptions to a reviewed base class. Exclude messages, custom class names, argument strings and tracebacks. Individual invalid selector lines retain their counted-skip contract.

Tests must cover each routing gate and alternative, threshold and interval boundary, actual predicate parity, input preservation, primary/replay scope, prospective OTHER, unavailable paths, wrapper restoration, condition-analysis failure, guard rollback, every error code, actual-module help exit and brief privacy/denominators. Existing-test failures are reported before any repair or expected-value change under the current user instruction.

## 10. Shadow routing rules

`own_adapter_route_diag.inspect_extraction(page, words, engine, extract, shadow=None)` appends one rule-to-branch mapping per call when `shadow` is a list. `own_adapter_shadow_route` evaluates CURRENT, OLD_CURRENT, A and S on the same captured payment inputs. CURRENT independently restates the operating predicate: OLD_CURRENT and no member-type value (직장가입/지역가입 in one grouped line after whitespace/bracket/colon/period/middle-dot removal; the operating `nhis_payment_gov.recognizes` applies the same definition). OLD_CURRENT is the earlier band predicate kept for before/after comparison; A and S replace only the header selection; paths without payment dispatch keep their actual branch. A rule exception yields the fixed ERROR branch. Observations are recorded for NHIS_PAYMENT reference pages only and are committed after the read-only guard exits, like route observations.

`summary.json.shadow_routes` holds rules, branches, routes (rule/engine/form/pages), cross (rule/engine/reference_form/form/pages, where reference_form is the same rule's text_layer branch) and checks (engine/match/mismatch for CURRENT against the actual route). Validate closed keys, enum values, integer counts and duplicate page paths before persistence. CURRENT mismatches and ERROR branches make the run exit 1. The route-condition analysis adds MEMBER_TYPE_ABSENT, and GOV_PREDICATE includes it. Only the member-type value rule (L_MEMBER_TYPE_VALUE) has been adopted into operating routing; other rules stay diagnostic.

## 11. Shadow candidates, D3 distribution and legacy marker

`inspect_extraction(..., candidates=None)` appends one record per call when `candidates` is a list: branches of A_325, A_350, B, L, A_325+L and A_350+L, the D3_BOSUOE/D3_INCOME interval names and the marker state O/X/NA. The existing `shadow` mapping keeps exactly the CURRENT/OLD_CURRENT/A/S keys. Candidate and marker rules use the OLD_CURRENT base (CURRENT inside their definitions and the CURRENT+L alias mean OLD_CURRENT), so L_MEMBER_TYPE_VALUE equals CURRENT. A_300 and CURRENT+L are aliases of A and L and are not evaluated twice. B uses the existing government reader's structure checks (payment_group_headers, payment_component_headers, payment_columns, monthly_rows_found, months_continuous) behind the unchanged gates. The marker is 가입구분 within one grouped line after whitespace/bracket/colon/period/middle-dot removal and must be absent from every government input observed by the engine suite.

`summary.json.shadow_candidates` holds rules, aliases, branches, routes, cross, distances (engine/measure/bin/pages) and markers (engine/marker/pages). Validate closed keys, enums, integer counts and duplicate page paths. Candidate ERROR branches make the run exit 1. Text families are CANDIDATE_RULES, CANDIDATE_ALIAS, CANDIDATE_ROUTE, CANDIDATE_CROSS, DIST3 and MARKER; SHADOW_* families stay restricted to CURRENT/OLD_CURRENT/A/S.

## 12. Legacy-marker candidates

`inspect_extraction(..., markers=None)` appends one record per call when `markers` is a list: the O/X/NA state of RRN_LABEL, MEMBER_CLASS_LABEL, LEGACY_ALIAS_LABEL, YEAR_MONTH_ROWS, MONTH_TABLE_ROWS and MEMBER_TYPE_VALUE and the branches of L_<marker> and L_<marker>+A_325. Markers are taken from the legacy reader's own clues. Phrase markers use one grouped line after whitespace/bracket/colon/period/middle-dot removal; structure markers use the legacy reader's year-month grammar and month-header search. No misread correction. Labels and structure take precedence over the value pattern MEMBER_TYPE_VALUE, which is tagged VALUE. A marker must be absent from the synthetic government pages and from every government reader fixture in the engine suite. Phrases found there (발급일, 발급일자, exact 년월, 보험료월, 사업장명칭) are not markers. Among inputs routed as government, 직장가입 appears only on the legacy-generated render grid of the shadow tests.

`summary.json.shadow_markers` holds markers (marker/kind), rules, branches, routes, cross and states (marker/engine/state/pages), validated with closed keys, enums, integer counts and duplicate page paths. Marker-rule ERROR branches make the run exit 1. Text families MARKER_CAND_RULES, MARKER_CAND_KIND and MARKER_CAND are new; the rules add CANDIDATE_ROUTE/CANDIDATE_CROSS rows after the existing candidate rows, and every earlier line stays unchanged. Operating routing and extraction stay unchanged.
