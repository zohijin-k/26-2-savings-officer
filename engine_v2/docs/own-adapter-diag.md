# Own/Apple adapter diagnostics

`engine_v2.tools.own_adapter_diag` measures page-local field agreement and reports conservative structural observations through the existing OCR baseline extraction path. It does not repair OCR output, change confidence, change service decisions, or establish the cause of a private document's failure.

Run from the repository root with installed local dependencies. Inputs/outputs must satisfy the existing external-or-ignored location policy. Use a new output directory for each invocation; existing output directories are rejected.

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.own_adapter_diag --root /tmp/FAKE-pdfs --out /tmp/FAKE-diag --engines own applevision
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.own_adapter_diag --root /tmp/FAKE-pdfs --ids /tmp/FAKE-payment.ids --out /tmp/FAKE-payment-diag --engines own applevision --fields NHIS_PAYMENT:MEMBERSHIP NHIS_PAYMENT:BILLING_MONTH NHIS_PAYMENT:ISSUE_DATE
```

`--limit N` limits attempted PDFs, including encrypted/open-error documents. PDF pages are evaluated separately. `--ids` accepts an immediate person-folder ID (select all inventoried PDFs below it) or a root-relative PDF path (select only that file). Blank lines and lines starting with `#` are ignored. Invalid/missing entries are skipped with numeric-only accounting; overlapping selections never process a PDF twice. Names select inputs only; they never hint document classification. With the default payment fields, nonpayment documents are skipped and counted, not relabeled as payment. Do not run an unknown input tree when preparing synthetic development evidence.

The default fields are the three payment fields above. `REGISTRY` in the tool provides the fixed ASCII code for every registered type/field pair. Other fields retain exact and normalized agreement measurements; unsupported causal evidence stays explicitly unattributable. Clean rendering and both actual local OCR callables are reused unchanged. A missing engine, OCR error, empty OCR, missing reference and classification failure have separate populations.

The extraction call is `ocr_baseline_runtime.extract → batch_assess._read_pages → localocr._from_supported_form → nhis_payment.extract`, with government forms delegated to `nhis_payment_gov.extract`. Observation wrappers always delegate to the original call and restore it on exit. The actual reference and observed branch are recorded as LEGACY/GOVERNMENT/OTHER, with null for unavailable paths; filenames and generator metadata do not choose a branch.

## Outputs and denominators

The four output files are `run.json`, `results.jsonl`, `summary.json`, `summary.txt`, and `summary_brief.txt`. Their closed schemas permit only fixed codes, integer document/page ordinals, finite numeric measurements and null. Text, values, input IDs/paths, coordinates, hashes, exception details and tracebacks are not diagnostic output. Dependencies execute under the existing quiet, read-only, no-network boundary.

- **Eligible** counts a present reference field. Reference absence is not a failed recognition.
- **Match opportunities** count completed comparisons with defined exact/normalized flags. Unsupported causal attribution does not erase a completed comparison. Execution failures and unavailable/empty OCR remain explicit without manufactured agreement rates.
- **Diagnosed** is the denominator for the thirteen mutually exclusive causal-code rates. Missing/unattributable evidence and availability/error states do not enter that denominator.
- Exact comparison uses typed raw field equality. Normalized comparison uses the existing symmetric semantic projection/canonicalization/masking. A normalized success is OK even when raw exact equality differs.
- A zero denominator produces null, including unmeasured form/field/engine cells.

Selection counters count valid folder/file lines, empty folders, invalid/missing/outside lines, duplicate selectors and overlapping PDF occurrences. Invalid/missing counts are per skipped line. A valid repeated selector, or a valid line adding no new PDFs because all its candidates were already selected, increments `duplicate_ids`; `overlapping_pdf_ids` counts the already-selected candidates on each valid line. An existing safe folder without PDFs is an empty-folder line, not a missing path.

`TYPE_NOT_REQUESTED` is a counted-zero page availability status. `skipped_documents` counts attempted documents with no requested-kind page, including input/quality/unknown exclusions. `classified_unrequested_documents` is the subset whose every page was confidently classified as another kind. `unrequested_pages` counts explicit TYPE_NOT_REQUESTED pages; unknown/quality exclusions remain separate. These are processing populations, not document verdicts.

The first supported causal condition wins:

| Code | Observation |
| --- | --- |
| OK | Existing normalized field comparison succeeds |
| ROUTE_MISMATCH | The measured field mismatches and the completed observed dispatch differs from the text-layer dispatch |
| LABEL_NOT_FOUND | A required reference-supported anchor is absent, including its permitted spacing/split/Unicode checks |
| LABEL_SPACED | Internal whitespace separates an otherwise supported anchor |
| LABEL_SPLIT | Spatially adjacent observations split the supported anchor |
| VALUE_NOT_FOUND | No matching, format-related or uniquely aligned candidate exists |
| VALUE_OTHER_LINE | The actual field requires one line/cell and a supported value falls on another line |
| LINE_MERGED | One uniquely aligned observed box corroborates the separate reference cells; a bounded copy split resolves the original extraction |
| ORDER | Equal token/geometry populations differ only in order and an original-path replay resolves the failure |
| NORMALIZE | A permitted normalization of a copy resolves the original-path extraction |
| PATTERN_MISMATCH | Unique, aligned literal components violate the existing format grammar |
| OCR_CHAR | A unique spatially supported candidate contains character errors |
| OTHER | Available evidence does not justify a more specific diagnosis |

Membership need not have a literal membership label. Billing-month lists require component evidence. Issue dates may be unlabeled and use a closing/issuing block; an unrelated print date is not their label. Counterfactuals operate only on copies and never replace measured extraction results or original confidence. The additional whitespace normalization removes U+200B ZERO WIDTH SPACE from a copy; it does not rewrite parentheses into date grammar or insert digits/separators.

Availability codes include separate input exclusions, reference absence/unattributability, classification failure, engine availability, OCR/extraction/empty-output states, and limit accounting. REFERENCE_ERROR, RENDER_ERROR and PROCESSING_ERROR describe execution failures with causal `counted=0`; they do not extend the thirteen-cause vocabulary.

Exit 0 means processing completed, including expected exclusions; 1 means execution-error records exist; 2 means argument/location/output/schema rejection; 130 means interruption. These are processing statuses, not document verdicts.

## Synthetic scope

Development uses newly authored inputs and tracked-source isolation. Preserve exact synthetic input bytes, settings, source identity and numeric results for later comparisons; put temporary PDFs, pytest files, DBs and uploads in a separately owned workspace. Retain long-lived results outside `/tmp` when comparisons may happen days later.

Legacy and government payment forms use different existing readers. Government membership is not emitted. Field-by-field reference availability must be reported, even for valid generated inputs. Synthetic/private form equivalence has not been verified: **합성·실서류 서식 차이 가능**. Do not infer private-document causes from synthetic distributions.

## Dispatch counts

`summary.json.routes.distributions` contains page counts for text_layer and each selected engine by LEGACY/GOVERNMENT/OTHER. `routes.cross` contains each engine's reference-form by observed-form cross-tabulation. `summary.txt` renders both as ROUTE and ROUTE_CROSS lines containing only fixed names and counts, including zero cells. Each completed path counts once per document/page across fields. A completed extraction counts even when its reference fields are absent. Reference counts include successful reference extraction on unrequested or classification-failed pages. OCR engines run only for requested types. An unavailable or failed path has a null form and contributes no dispatch count.

On a present-reference mismatch, ROUTE_MISMATCH precedes classification/label/value/evidence diagnoses. OK retains first priority. Reference absence and execution/availability errors retain their status. Dispatch agreement and field agreement therefore have separate denominators.

## Routing conditions and compact output

The diagnostic observes the prepared input received by the original payment reader and its government predicate. CONDITION rows report each gate as O/X counts. CONDITION_PATTERN rows pair the ordered O/X combination with the actual route and page count. Reference-form and engine columns keep legacy/government populations separate. Each path counts once per page across fields. PAYMENT_DISPATCH_CALLED X and PROSPECTIVE identify a completed OTHER path whose prepared inputs were analyzed separately. Availability/error paths contribute status counts and zero measured patterns.

CONDITION_ORDER prints the full fixed order. BIN rows define each half-open interval as metric, interval name, inclusive lower and exclusive upper bound. INF is an unbounded upper limit and NA identifies unavailable measurements. DISTRIBUTION rows expose page counts per interval without raw document measurements.

- HEADER_BOSUOE_COUNT and HEADER_INCOME_COUNT use N0, N1, N2, N3, N4_9 and GE10.
- HEADER_HEIGHT_RATIO is the original search-band height, three first-month box heights divided by page height before component trimming. Boundaries are .01, .02, .05, .10 and .25. A missing first month yields NA.
- BOX_HEIGHT_MEDIAN_RATIO uses .005, .01, .02, .05 and .10.
- BOX_CHAR_MEDIAN measures whitespace-squashed NFKC/masked text length per prepared box, then takes its median. Boundaries are 1, 4, 8, 16, 32 and 64.
- PAGE_BOX_COUNT uses ZERO, N1_49, N50_99, N100_199, N200_399, N400_799 and GE800.

Paste summary_brief.txt for review. It contains ROUTE/ROUTE_CROSS, condition order, interval definitions, O/X counts, nonzero histogram/pattern rows and nonzero field-code rows. FIELD_POPULATION columns are eligible, match opportunities and diagnosed counts. CONDITION_STATUS records unavailable paths, CONDITION_ERROR and PREDICATE_DIVERGENCE. The latter two make the run exit 1 while retaining the preceding field measurements.

For the broad-header hypothesis, compare HEADER_HEIGHT_RATIO and BOX_HEIGHT_MEDIAN_RATIO distributions across engines within the same reference form, then HEADER_BOSUOE_GE3/HEADER_INCOME_GE3 and their pattern-to-route rows. For the fused-month hypothesis, compare COMPONENT_TOP_FOUND, FIRST_MONTH_FOUND and HEADER_COMPONENT_TOP_FOUND with BOX_CHAR_MEDIAN. FIRST_MONTH_FOUND X by itself leaves absent, fused and spatially excluded month tokens unresolved. FIRST_MONTH_FOUND O shows that at least one eligible complete month token survived. It refutes the specific claim that all month candidates were lost to full-match failure on that page.

## Shadow routing rules

The diagnostic also evaluates candidate header rules on the exact payment inputs the operating dispatch received, without changing routing or extraction. CURRENT restates the operating band (from three first-month box heights above the first month top). A keeps the words whose centres lie in [C-3H, C-0.5H), where H is the median positive box height and C the first-month centre. S keeps the contiguous header-line block directly above the first month: lines nearest first (0.3H line tolerance) are accepted upward until a centre gap above 1.5H, a line containing 고지금액/납부금액, or a line without header vocabulary. Every rule keeps the title, document-number and information-grid gates, the component-top cut, clustering and the three-repetition counts. A path without an observed payment dispatch keeps its actual branch under every rule.

SHADOW_ROUTE rows give rule, engine (text_layer or OCR engine), branch (LEGACY, GOVERNMENT, OTHER or ERROR) and page count. SHADOW_CROSS rows give rule, OCR engine, the same rule's text_layer branch, the engine branch and page count. SHADOW_CHECK CURRENT rows give, per engine, pages where CURRENT equals the actual route (MATCH) and pages where it differs (MISMATCH). A mismatch or an ERROR branch makes the run exit 1. summary.txt prints every cell. summary_brief.txt prints every SHADOW_ROUTE cell except zero ERROR cells, nonzero SHADOW_CROSS cells and every SHADOW_CHECK row. These rows contain only fixed codes and counts.

## Candidate rules, position distribution and legacy marker

A separate section evaluates further candidates on the same captured payment inputs; the CURRENT, A and S rows above are unchanged. A_325 and A_350 are A with the far bound at C-3.25H and C-3.50H (near bound C-0.5H). A_300 would be identical to A and is printed only as an alias. B keeps the title and metadata gates and then requires the government table structure itself, as checked by the existing government reader: both group headers, the nine aligned column headers, eight amount-column boundaries and continuous months 1 to 12. L returns LEGACY when the legacy-only marker is present and otherwise CURRENT; CURRENT+L is the same rule and is printed as an alias. A_325+L and A_350+L apply the marker first and otherwise the band rule.

The legacy-only marker is 가입구분, searched in every grouped line after removing whitespace, square and round brackets, colons, periods and middle dots, so labels split into several boxes on one line still match. No character-confusion correction is applied; a misread label counts as absent. A vertically split label is not joined.

CANDIDATE_RULES and CANDIDATE_ALIAS rows name the candidates. CANDIDATE_ROUTE and CANDIDATE_CROSS rows have the same columns as SHADOW_ROUTE and SHADOW_CROSS. DIST3 rows give engine, BOSUOE or INCOME, a distance interval and page count. The distance is the third-nearest upward centre distance, in H, from the first-month centre to words containing 보수외 (or 소득월액); fewer than three such words, no first month or no payment dispatch give NA. Intervals are 0.000-2.000, 0.125H steps from 2.000 to 4.000, 0.5H steps from 4.000 to 6.000, 6.000+ and NA, each closed below and open above. MARKER rows give engine, O, X or NA (no payment dispatch) and page count. summary.txt prints every cell. summary_brief.txt prints the rule and alias rows, every CANDIDATE_ROUTE cell except zero ERROR cells, nonzero CANDIDATE_CROSS and DIST3 cells and the O/X MARKER cells (NA only when nonzero). A candidate ERROR branch makes the run exit 1. The rows contain only fixed codes, interval names and counts.

## Legacy-marker candidates

Six further markers come from the clues the legacy reader itself uses, and each gives two rules: L_<marker> returns LEGACY when the marker is present and otherwise CURRENT, and L_<marker>+A_325 returns LEGACY when the marker is present and otherwise A_325. RRN_LABEL is 주민등록번호 (the legacy header reads the birth date through it). MEMBER_CLASS_LABEL is 가입구분 or 가입자구분. LEGACY_ALIAS_LABEL is any legacy reader label alias the government form does not use: 고지보험료, 납부보험료, 실납부, 출력일 or 발행일. These three and MEMBER_TYPE_VALUE are searched in one grouped line after removing whitespace, brackets, colons, periods and middle dots, with no character-confusion correction and no joining across lines. YEAR_MONTH_ROWS needs at least three grouped lines whose leftmost box, without whitespace, is entirely a year-month in the legacy reader's grammar (MONTH_RE or COMPACT_MONTH_RE after its dash unification). MONTH_TABLE_ROWS needs the legacy month-column header (the legacy reader's own header search) and at least three following lines carrying a year-month before a 합계, 납부총액, 확인합니다 or 국민건강보험공단 line. MEMBER_TYPE_VALUE is 직장가입 or 지역가입; it is a value pattern, not a label, and is marked VALUE. Every marker is absent from the synthetic government pages and from every government input the engine suite routes.

MARKER_CAND_RULES lists the twelve rules and MARKER_CAND_KIND gives each marker's kind (LABEL, STRUCTURE or VALUE). MARKER_CAND rows give marker, engine, O, X or NA (no payment dispatch or a marker failure) and page count. The rules add CANDIDATE_ROUTE and CANDIDATE_CROSS rows after the earlier candidate rows; CANDIDATE_RULES, CANDIDATE_ALIAS, DIST3 and MARKER rows are unchanged. summary.txt prints every cell; summary_brief.txt prints the O/X MARKER_CAND cells (NA only when nonzero), every CANDIDATE_ROUTE cell except zero ERROR cells and nonzero CANDIDATE_CROSS cells. A marker failure records ERROR for its twelve rules and makes the run exit 1. The rows contain only fixed codes and counts.

Use --help for static usage with exit 0. CLI failures return code 2 and distinct ROOT_NOT_DIR, OUT_EXISTS, OUT_INSIDE_ROOT, ROOT_INSIDE_OUT, IDS_NOT_FOUND, IDS_INVALID, SYMLINK_REJECTED, LOCATION_REJECTED or OUTPUT_ERROR codes. Unknown/missing/invalid argument selections return ARGUMENT_ERROR. Remaining exceptions return UNEXPECTED_ERROR with a reviewed built-in exception_type. Error messages contain zero input values or paths. Invalid individual list lines keep their existing numeric skipped-line accounting.
