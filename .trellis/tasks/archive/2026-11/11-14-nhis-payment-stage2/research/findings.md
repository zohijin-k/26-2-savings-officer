# Investigation findings

## Evidence and limits

Inspected the five explicitly authorized masked JSON dumps and repository code only. No source PDFs, private inventories, database contents or external document files were opened. Dumps were read in memory and were not passed to extraction, date parsing or numeric parsing. Geometry-only inspection reconstructed line/cluster membership. Nothing below copies a masked value or source coordinate. Fixed code-owned labels are cited as code vocabulary, not recovered source text.

Ran transient probes using the existing fictitious payment fixture and independently authored modifications. No product code, existing tests or fixture providers changed. These are investigation experiments, not the permanent regression suite or a real-document rerun. The full synthetic v2 before/after measurement remains an implementation-phase gate.

## 1. Query periods: distinguish range parsing from row reconciliation

All five own diagnostics select `government_payment` and none fails `payment_query_period`. That check requires exactly one complete pre-table period row, one valid same-year range, and no unsupported residue (`nhis_payment_gov.py:320`). The range-shaped metadata is one observation in own and Apple, while each text reference divides it into six observations: year, month, separator, year, month, caption. The unit annotation is on a following line. All range observations are above the table, have ordinary ASCII tilde punctuation, and exceed the independent period confidence threshold. Dots appear in other date-shaped metadata; they do not demonstrate a broken range separator.

Consequently the supplied evidence does **not** support period splitting, tilde damage, dot damage or page position as the cause of these five own outcomes. `payment_period._period` removes whitespace before matching and accepts the government reader's range/caption grammar (`payment_period.py:20`). It has a different, intentional confidence and row reconciliation contract.

`payment_period.collect` scans pre-table range evidence, then independently checks leftmost month rows even when extraction failed to establish columns (`payment_period.py:60`, `:86`). Every digit-only token on a row can contribute a positive observation, with no amount-column bound (`:105`). Outside the range, unrecognized values make evidence uncertain (`:110`), and any positive or explicit-year row makes it conflicting (`:118`). A low-confidence positive still produces CONFLICT because conflict takes precedence in the final status (`:148`). OCR zero lookalikes are accepted as zeros only when the existing full arithmetic checks succeeded (`:38`).

| Own diagnostic | Supported interpretation | Limit |
| --- | --- | --- |
| p001 / p005: PERIOD_UNCERTAIN_OR_MISSING | A successfully parsed government range can coexist with independent uncertainty. Body rows contain letter-shaped/non-numeric observations and failing table/arithmetic checks, so corrected zeros cannot automatically discharge that uncertainty. | The mask cannot distinguish an allowed zero lookalike from another letter. Extra masked label text also cannot be decoded. The exact word triggering uncertainty cannot be proved. |
| p002 / p006: PERIOD_CONFLICT | There is only one range-shaped pre-table candidate and no explicit-year body month shape. The independent conflict therefore points to positive out-of-range row evidence rather than two merged provider results. Low-confidence extra numeric observations exist in the body. | The mask erases zero versus positive and the actual query endpoints. It cannot identify the contributing month/cell or establish that the positive is an OCR hallucination. |
| p010: MONTHLY_MAP_MISSING_OR_UNREADABLE | Range evidence is readable; component-header/column failure prevents monthly-map output. Twelve observed month anchors alone do not establish readable amounts. | A range or month count cannot replace the missing numeric map. |

Synthetic probes confirmed: a normal range and annual zero placeholders yield READABLE; one unknown letter outside the range yields UNDETERMINED; an allowed zero correction with proven arithmetic yields READABLE; a positive outside the range yields CONFLICT. Whitespace-split year/month digits and dotted numeric ranges parse; an unsupported tilde variant or extra dots after Korean month suffixes do not. The latter two are grammar boundaries, **not demonstrated defects in the supplied dumps**.

Recommendation: keep independent conflict, unreadable-value and correction gates. Do not discard low-confidence positives, infer zeros or expand punctuation grammar from this evidence. Structural repairs can restore valid arithmetic and thereby unblock the already-approved zero-correction path, but this is not a guarantee that any private case will pass.

## 2. Actual text-layer upload and batch data flow

`upload_assessment.assess_upload` calls the supplied/default reader once (`demo/backend/upload_assessment.py:58`). Normal `read_document` tries its adapter chain and stops on the first result (`demo/backend/ocr/__init__.py:34`). Its introductory comment about all text PDFs bypassing LocalOcr is stale; executable code is authoritative.

For supported payment text PDFs, `LocalOcr._read` uses `pdftext._read_pdf` for content classification, then invokes `_load_pages` and the payment extractor (`localocr.py:663`, `:696`, `:742`). `_from_supported_form` scopes attachments before conversion (`:517`). On each page with sufficient text, preprocessing chooses TEXT_LAYER, and `_load_pages` constructs words from PyMuPDF `get_text("words", sort=True)`, scales boxes and assigns confidence 1.0 (`engine_v2/pipeline/preprocess.py:91`, `engine_v2/engine.py:173`). It bypasses native OCR for that page. Sparse/partial text pages can independently take the OCR path; the first-page Tier2 probe and the per-page text sufficiency test are different thresholds.

`_from_nhis` copies extracted fields and computes `고지월검증자료` from the **same** scoped pages (`localocr.py:363`, `:398`). `_check_billing_months` prioritizes that independent evidence, then requires the monthly map when applicable (`rules/doc_check.py:395`). A valid map cannot override a conflict. This reconciles two kinds of evidence from one word source; it does not merge text and own results. Original `classified.fields` are not merged into payment fields.

Batch measurement intentionally differs:

1. `_inspect` renders every PDF page in memory and separately builds reference words (`batch_assess.py:454`).
2. `_engine(..., "own")` recognizes the raster, then `_read_pages` runs the shared extractor/converter on those words (`:587`, `:518`).
3. `process_one` retains `own_ocr` and supplies it to `_assess` (`:715`). `_assess` injects `reader=lambda ...: ocr` into `assess_upload` (`:633`). Normal reader routing is therefore bypassed deliberately.
4. The text reference is computed later for field agreement (`:739`). Its converted result is discarded; it is neither assessed for the top-level verdict nor merged with own.

Thus a PDF having a normal text reference and a batch MISSING_BILLING_MONTHS is consistent with the code: the latter describes forced own OCR. The five dumps support that mechanism, not a numeric explanation of all 111 user-reported cases. No private batch artifact was opened. Recommend synthetic routing/parity regression tests and a scoped explanatory documentation correction, not a change to batch assessment policy or shared readers.

## 3. Apple/text references use the legacy reader

All five Apple diagnostics and both text references select `legacy_payment`; all five own diagnostics select `government_payment`. The matched-of-nine metric measures government recognition/table clusters, not universal extraction success (`tools/structure_dump.py:167`, `:215`). Zero government matches can therefore coexist with twelve legacy months.

Government recognition bounds its header search by three times the **first month word's height** (`nhis_payment_gov.py:31`). Smaller month boxes in Apple/text shrink that window and omit the upper tier of multi-line component headings. In all five Apple dumps the short upper fragments fall outside that recognition window; text-reference upper fragments are split further and likewise excluded. This is a demonstrated provider-geometry sensitivity, not a provider-specific parser.

An authored probe that only shortened month boxes switched the same fictitious content from government to legacy, retained month output, and failed `monthly_total_matches`—matching the qualitative Apple pattern.

Legacy extraction finds month/header labels through `common.label_hits`, finds month-only rows using the title year, and chooses nearby amounts by header centers (`nhis_payment.py:168`, `:244`, `:280`). It does not prove all eight printed amount columns or require an observed total (`:494`: absent totals do not fail). Every Apple dump still fails monthly_total_matches; `_from_nhis` recognizes that critical check and caps confidence. Billing cause NONE means no billing-month finding; it does **not** mean overall PASS.

Recommendation: do not reroute a failed government form to legacy, copy Apple values, or waive missing headings. Reuse only the comparison-view idea while retaining all government label/order/body-corridor/arithmetic guards. Reader-selection window stabilization is deferred because switching Apple/text to another reader is a separate compatibility change and the masks do not expose all component spellings.

## 4. p001: row assignment cascades into all column sums

p001 own proves nine component headings and payment_columns/payment_sum_row. Its twelve month rows each have a month observation and eight horizontally separated amount observations. An additional non-month row sits between the last month and the sum row, with a label-shaped observation and four amounts in corresponding billed/paid component positions. The mask does not reveal that row's original label or amounts.

`_monthly_table` includes everything through the sum row in `body` (`nhis_payment_gov.py:193`). It assigns every non-sum word to the closest month (`:201`), even when its distance fails the row-band limit. The extra row is assigned to the last month. The combined month cell no longer equals that month's label (`:218`), so the last row is omitted from `values`. Global `rows_ok` and `len(values) == 12` then gate **all eight** sum checks (`:252`). Fourteen failed validations do not imply eight independent numeric misreads.

An authored `연말정산` row in that position, with four exact zeros and otherwise unchanged correct fictitious numbers, reproduces monthly_amounts_numeric, monthly_total_matches, all eight payment_column sum failures, and missing monthly-map output. The extractor already supports that code-owned label in the legacy path (`nhis_payment.py:222`), but the government reader has no corresponding adjustment-row handling.

Conclusion: a structural **row** assignment failure is demonstrated; the evidence does not establish a cross-column assignment error. Numeric/letter recognition problems may coexist and cannot be decoded from the mask. Supporting only a positively identified, bounded `연말정산` row can fix the reproduced cause without ignoring unknown extra rows. If the private label is different, it must remain reviewable.

## 5. Two independent own header geometry failures

- p006: two short upper-tier observations straddle the group-header lower edge. Government recognition sees them, but the table reader's `word.y0 > group_bottom` removes them (`nhis_payment_gov.py:185`). Their vertical centers are below that edge. Nine clusters remain but only seven complete labels match. An authored overlap reproduces component-header/column/paid-total failure without changing text or values.
- p010: the half-glyph proximity rule joins a wider care-heading observation and the next component's fragments (`:121`). It produces eight clusters rather than nine and contaminates one component cluster. An authored neighboring-header expansion reproduces the same classes of failure. This is distinct from missing source text and from the p006 band clipping.

Recommendation: two separate payment-only fixes and test groups. Retain original words/bounds. For band overlap, use observed heading roles/relative center placement while requiring a complete ordered header set and no unexplained header evidence. For proximity fusion, allow a uniquely validated subdivision against observed body corridors and complete ordered component spellings; never relax the global gap constant or invent a label. If uniqueness cannot be established, keep review. Body artifacts that erase or ambiguously divide amount corridors (notably p002/p005) remain deferred; confidence alone cannot justify dropping them.

## Disposition

Proposed fixes: explicit bounded adjustment-row support; component band clipping; uniquely resolvable component-cluster fusion. Proposed tests/documentation: period conservatism, batch/reference routing and provider reader selection. Deferred: numeric OCR improvement, unidentified extra labels, body-noise filtering, independent conflict suppression, grammar expansion and broad reader rerouting. No code was fixed during planning.
