# Stage 2-1 completion report — commit approval pending

The diagnostic now observes the original payment predicate inputs and exposes fixed O/X condition counts, structural histogram bins and condition-pattern to actual-route cross-tabulations. Static help, distinct errors and summary_brief.txt are implemented. The operator supplied the earlier 120-page aggregate observations recorded in research/route-conditions.md. Private input/result accesses in this stage are zero.

## Actual routing and inputs

| Function | Role and condition | Input |
| --- | --- | --- |
| pdftext.classify_with_evidence / classify_pages_with_evidence | Ordered document keywords select payment, another type or unknown. Coordinate fallbacks follow missing keyword classification. | Whitespace-squashed text, then geometry for fallback families |
| batch_assess._read_pages / localocr._from_supported_form / attached_pages.extract_form | Delegates a classified payment page to nhis_payment.extract. Single-page partition keeps the page intact. | Shared prepared pairs |
| nhis_payment.extract | Government recognizes true delegates to nhis_payment_gov.extract. False continues into the legacy reader. Its later title validation does not select the route. | Exact prepared extraction pairs |
| nhis_payment_gov.recognizes | GOV_TITLE and (GOV_NUMBER_GATE or INFO_GRID_GATE) and HEADER_BOSUOE_GE3 and HEADER_INCOME_GE3 | Joined text, component boundary, first-month box, header geometry/clustering |
| own_adapter_diag_evidence.extract_with_form | Observes GOVERNMENT/LEGACY result paths. OTHER identifies absence of payment extraction. Unavailable extraction has a null route. | Actual delegated calls/results |

Text-layer inputs originate from rotated/scaled PyMuPDF word boxes. Own emits one word object per expanded detected crop and can retain a whole text line in that box. Apple Vision forwards one provider observation and converts bottom-left normalized bounds to top-left pixels. Shared preparation deep-copies, applies NFKC/masking and preserves geometry/confidence. page_lines converts coordinates to page percentages and groups vertical centers with tolerance .6 and a .3-percent minimum height. Header regrouping uses .25 and horizontal clusters use half the median glyph width. Joined text uses 15-pixel y ordering. squash removes whitespace. The document-number predicate additionally maps the existing dash variants. The complete condition definitions and source files are in research/route-conditions.md.

## Verification

- New independent tests 108 passed. Existing focused diagnostics 127 passed. Full engine_v2 1983 passed / 3 skipped / 3 xfailed. The pass growth is 1983 − 1875 = 108, equal to collected new tests. Original test-file/expectation edits are zero.
- The preserved corpus contains 111 identical restored PDFs. The selected payment subset is the original 70 pages, reference LEGACY 50 / GOVERNMENT 20. Native diagnosis completed 420 field records and 210 condition page-paths with execution errors 0, empty OCR 0 and condition/parity errors 0.
- Original results.jsonl and run.json are byte-identical to the preceding accepted diagnosis. Every preceding summary.json section matches, and summary.txt retains the complete preceding text as its prefix. New output is additive. Protected engine/backend source identities match on 366 files outside the permitted documentation updates.
- Changed paths satisfy the approved four-directory boundary. ENGINE_V2_ONLY follows from the path lists below. AST parsing, context-manifest validation and diff hygiene passed. Installed dependency warnings remain visible in pytest logs.

## Synthetic condition counts

Each cell below is the O page count. The X count is the column population minus O. All 210 paths have MEASURED status.

| Condition in pattern order | LEGACY text_layer (50) | LEGACY own (50) | LEGACY applevision (50) | GOVERNMENT text_layer (20) | GOVERNMENT own (20) | GOVERNMENT applevision (20) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PAYMENT_DISPATCH_CALLED | 50 | 50 | 50 | 20 | 20 | 20 |
| GOV_TITLE | 50 | 50 | 50 | 20 | 20 | 20 |
| DOCUMENT_NUMBER_LABEL | 0 | 0 | 0 | 20 | 20 | 20 |
| DOCUMENT_NUMBER_PATTERN | 0 | 0 | 0 | 20 | 20 | 20 |
| GOV_NUMBER_GATE | 0 | 0 | 0 | 20 | 20 | 20 |
| PAYER_NUMBER_LABEL | 0 | 0 | 0 | 20 | 20 | 20 |
| WORKPLACE_LABEL | 0 | 0 | 0 | 20 | 20 | 0 |
| INFO_GRID_GATE | 0 | 0 | 0 | 20 | 20 | 0 |
| COMPONENT_TOP_FOUND | 50 | 0 | 0 | 20 | 20 | 20 |
| FIRST_MONTH_FOUND | 0 | 0 | 0 | 20 | 20 | 20 |
| HEADER_COMPONENT_TOP_FOUND | 0 | 0 | 0 | 20 | 20 | 20 |
| HEADER_BOSUOE_GE3 | 0 | 0 | 0 | 20 | 0 | 20 |
| HEADER_INCOME_GE3 | 0 | 0 | 0 | 20 | 20 | 20 |
| GOV_PREDICATE | 0 | 0 | 0 | 20 | 0 | 20 |
| LEGACY_TITLE | 50 | 50 | 50 | 20 | 20 | 20 |

## Synthetic distributions

| Metric | LEGACY text_layer | LEGACY own | LEGACY applevision | GOVERNMENT text_layer | GOVERNMENT own | GOVERNMENT applevision |
| --- | --- | --- | --- | --- | --- | --- |
| HEADER_BOSUOE_COUNT | N0 50 | N0 50 | N0 50 | N4_9 20 | N1 10, N2 10 | N4_9 20 |
| HEADER_INCOME_COUNT | N0 50 | N0 50 | N0 50 | N4_9 20 | N4_9 20 | N4_9 20 |
| HEADER_HEIGHT_RATIO | NA 50 | NA 50 | NA 50 | R005_010 20 | R005_010 20 | R005_010 20 |
| BOX_HEIGHT_MEDIAN_RATIO | R001_002 50 | R001_002 50 | R001_002 50 | R001_002 20 | R001_002 20 | R001_002 20 |
| BOX_CHAR_MEDIAN | R4_8 50 | R4_8 50 | R4_8 50 | R1_4 20 | R1_4 20 | R1_4 20 |
| PAGE_BOX_COUNT | N1_49 50 | N1_49 50 | N1_49 50 | N100_199 20 | N100_199 20 | N100_199 20 |

Intervals and inclusive/exclusive edges are specified in design.md and printed as BIN rows in every brief. Only binned measurements are serialized.

## Synthetic condition-pattern cross-tabulation

| Reference form | Engine | Pattern | Actual route | Pages |
| --- | --- | --- | --- | ---: |
| LEGACY | text_layer | OOXXXXXXOXXXXXO | LEGACY | 50 |
| LEGACY | own | OOXXXXXXXXXXXXO | LEGACY | 50 |
| LEGACY | applevision | OOXXXXXXXXXXXXO | LEGACY | 50 |
| GOVERNMENT | text_layer | OOOOOOOOOOOOOOO | GOVERNMENT | 20 |
| GOVERNMENT | own | OOOOOOOOOOOXOXO | LEGACY | 20 |
| GOVERNMENT | applevision | OOOOOOXXOOOOOOO | GOVERNMENT | 20 |

## Hypotheses assessed against the 70 pages

| Hypothesis | Supporting/refuting measurements | What remains unresolved |
| --- | --- | --- |
| H1 tall own boxes broaden the header band and admit repeated body text | On government pages all three paths occupy HEADER_HEIGHT_RATIO R005_010 20 and BOX_HEIGHT_MEDIAN_RATIO R001_002 20. Own header repetitions are N1 10 / N2 10, while text/Apple are N4_9 20. No higher-band or excess-repetition evidence supports H1 in this subset. On legacy pages all paths have header height NA 50 and both repetition counts N0 50. | Equal coarse bins permit different values within a bin. Legacy pages have no valid first month and their government metadata gates are zero, so the current corpus cannot exercise the reported operator false-government direction. |
| H2 fused month boxes fail MONTH.fullmatch and cause the synthetic own government-to-legacy route | Own government FIRST_MONTH_FOUND O 20 and HEADER_COMPONENT_TOP_FOUND O 20, equal to text/Apple. Each page therefore retains at least one eligible complete month token. HEADER_BOSUOE_GE3 X 20 is the failing route gate, with count N1 10 / N2 10. This refutes loss of every month candidate as the cause for these 20 routes. | Some other month boxes could still be fused. Count-only output leaves recognition loss versus string-reassembly loss of the exact header substring unresolved. Legacy FIRST_MONTH_FOUND X 50 also occurs in the text reference and is consistent with its different year-month notation. |

Independent authored-token tests confirm that doubling a month box height can widen the original band and flip the original government predicate, and that a fused month/amount box can fail the full-match gate. Those tests establish possible mechanisms. The preserved 70-page observations above determine which mechanism was exercised here.

## Rows to inspect in the operator brief

Use the LEGACY reference-form rows because all 120 operator reference pages were LEGACY. Compare own with text_layer and applevision.

- H1 uses DISTRIBUTION LEGACY <engine> HEADER_HEIGHT_RATIO and BOX_HEIGHT_MEDIAN_RATIO, then CONDITION LEGACY <engine> HEADER_BOSUOE_GE3 / HEADER_INCOME_GE3 and CONDITION_PATTERN LEGACY <engine>. Higher own height intervals together with only-own >=3 repetition gates support the broad-band hypothesis. Check GOV_TITLE and GOV_NUMBER_GATE or INFO_GRID_GATE in the same O/X patterns to verify the other route requirements. Divergent metadata gates would identify an additional cause.
- H2 uses CONDITION LEGACY <engine> COMPONENT_TOP_FOUND / FIRST_MONTH_FOUND / HEADER_COMPONENT_TOP_FOUND, together with DISTRIBUTION LEGACY <engine> BOX_CHAR_MEDIAN and HEADER_HEIGHT_RATIO. Own FIRST_MONTH_FOUND X with reference/Apple O is consistent with loss of eligible full-match candidates. X alone cannot distinguish absent text, fusion or spatial exclusion. FIRST_MONTH_FOUND O refutes loss of every eligible candidate for that page population. Read CONDITION_ORDER to decode each CONDITION_PATTERN row.
- Read CONDITION_POPULATION and CONDITION_STATUS first. MEASURED counts are actual primary calls. PROSPECTIVE describes an OTHER path. Error/unavailable statuses contribute zero O/X patterns. FIELD_POPULATION prints eligible, comparison and causal denominators. FIELD rows contain only nonzero causal/status counts.

## Future synthetic reproduction candidates

The current legacy 50 pages have GOV_NUMBER_GATE O 0 and INFO_GRID_GATE O 0 for all paths. Merely changing resolution, font size or row placement cannot reliably supply absent metadata text. A future approved legacy fixture should contain legitimate payment metadata while the text-layer predicate stays legacy, plus repeated component labels outside the intended narrow band. Font size, month-box height, row gaps, skew and table placement can then test whether own detection broadens the selected band enough to count those labels. For the fused-month hypothesis, vary month/amount gaps and font size while keeping labels and component boundaries fixed. For the newly observed repeated-header failure, vary stacked-header gaps, horizontal spacing and font width to distinguish detection granularity from cluster/line reassembly. This stage changes zero generators.

## Changed-file purpose

- engine_v2/tools/own_adapter_diag.py adds primary observation plumbing, additive summaries/brief and CLI usability/error handling.
- engine_v2/tools/own_adapter_route_diag.py implements closed condition/bin observations and page-based aggregation.
- engine_v2/tests/test_own_adapter_route_diag.py adds 108 independent tests. Existing test files retain their preceding bytes.
- engine_v2/docs/own-adapter-diag.md and .trellis/spec/backend/own-adapter-diagnostics.md document the exact output/error contract.
- The same task PRD/design/implementation/context/metadata, route research and this report preserve approval, source reasoning, results and verification.

## Regression scope evidence

`git diff --name-only main...HEAD` at precommit review

```text
.trellis/spec/backend/index.md
.trellis/spec/backend/own-adapter-diagnostics.md
.trellis/tasks/11-15-own-adapter/check.jsonl
.trellis/tasks/11-15-own-adapter/design.md
.trellis/tasks/11-15-own-adapter/implement.jsonl
.trellis/tasks/11-15-own-adapter/implement.md
.trellis/tasks/11-15-own-adapter/prd.md
.trellis/tasks/11-15-own-adapter/research/adapter-contract.md
.trellis/tasks/11-15-own-adapter/research/corpus-command.md
.trellis/tasks/11-15-own-adapter/research/source-map.md
.trellis/tasks/11-15-own-adapter/review-stage1.md
.trellis/tasks/11-15-own-adapter/stage0-complete.md
.trellis/tasks/11-15-own-adapter/stage0-stop.md
.trellis/tasks/11-15-own-adapter/stage1-report.md
.trellis/tasks/11-15-own-adapter/task.json
engine_v2/docs/own-adapter-diag.md
engine_v2/tests/test_own_adapter_diag.py
engine_v2/tests/test_own_adapter_diag_codes.py
engine_v2/tools/own_adapter_diag.py
engine_v2/tools/own_adapter_diag_evidence.py
```

Working-tree changed paths at precommit review, including the new report

```text
.trellis/spec/backend/own-adapter-diagnostics.md
.trellis/tasks/11-15-own-adapter/check.jsonl
.trellis/tasks/11-15-own-adapter/design.md
.trellis/tasks/11-15-own-adapter/implement.jsonl
.trellis/tasks/11-15-own-adapter/implement.md
.trellis/tasks/11-15-own-adapter/prd.md
.trellis/tasks/11-15-own-adapter/research/route-conditions.md
.trellis/tasks/11-15-own-adapter/stage21-report.md
.trellis/tasks/11-15-own-adapter/task.json
engine_v2/docs/own-adapter-diag.md
engine_v2/tests/test_own_adapter_route_diag.py
engine_v2/tools/own_adapter_diag.py
engine_v2/tools/own_adapter_route_diag.py
```

Every listed path starts with engine_v2/tools/, engine_v2/tests/, engine_v2/docs/ or .trellis/. The user-approved rule therefore selects engine_v2 verification. The final staged list equals the 13 working-tree paths above. The five supplied pattern counts over the whole staged diff are 0 / 0 / 0 / 0 / 0. Exact paths and counts are also reported in chat. The proposed commit is tools: add payment route condition diagnostics. Commit approval is pending. Operator commands with fully specified private paths are confined to chat. Stage 2-2 follows the operator results and a separate instruction.
