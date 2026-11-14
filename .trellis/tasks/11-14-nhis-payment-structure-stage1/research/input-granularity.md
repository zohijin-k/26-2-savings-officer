# Research: NHIS_PAYMENT input granularity

- **Query**: Identify input-unit assumptions in payment header, column and monthly-row extraction, compare text-layer/own/Apple Vision input, and document the fixed-label vocabulary usable by a masked structural dump.
- **Scope**: Local source code and authored synthetic coordinate fixtures only. No real documents were opened, located or requested.
- **Date**: 2026-11-14

## Findings

### Conclusion

The proposed explanation is **partly supported as a granularity/geometry sensitivity, but not supported as a line-only extractor contract**. All three providers expose `list[OcrWord]`; the common extraction layer normalizes their coordinates and reconstructs lines. The government payment reader explicitly supports split component headers and geometric columns, and existing tests exercise glyph/header fragments. Conversely, several checks require a month in one word, exact reconstructed header clusters, and body boxes that do not cross column boundaries. Both over-merging and over-splitting can change the selected reader or lose table evidence.

The supplied aggregate measurements establish a discrepancy worth investigating, not its exact cause. This research does not attribute the real-document failures to any single check.

### Files and data flow

| Source anchor | Confirmed behavior |
|---|---|
| `engine_v2/pipeline/ocr/__init__.py:25` | `OcrWord` carries text, confidence and a top-left pixel bbox. There is no provider-neutral character/word/line semantic tag. |
| `engine_v2/engine.py:173` | `_load_pages` handles text-layer PDFs separately from OCR pages. |
| `engine_v2/engine.py:188` | Text-layer words use `page.get_text("words", sort=True)`, retain PyMuPDF token boxes, discard its block/line/word-number fields, scale points by 300/72 and assign confidence 1.0. No extractor-specific token splitting is performed. |
| `engine_v2/pipeline/ocr/own.py:65` | Own detects connected regions/contours, filters and expands their quadrilateral boxes. |
| `engine_v2/pipeline/ocr/own.py:114` | Own recognizes one crop for each detected box and returns one `OcrWord` for each nonempty recognized text. These are detected text regions, not guaranteed single characters or linguistic words. |
| `engine_v2/pipeline/ocr/own.py:136` | Own sorts results by `(round(y0 / 15), x0)` before returning. |
| `engine_v2/pipeline/ocr/__init__.py:64` | Apple Vision wraps each `(text, confidence, normalized box)` observation from `ocrmac` as one `OcrWord`, flips the lower-left normalized origin to top-left pixels, and does not split its text. The adapter does not guarantee one physical line per observation. |
| `engine_v2/pipeline/ocr/__init__.py:43` | `OcrResult.text` separately sorts words with the same 15-pixel y bucket. This string view is used by some detection/period checks and is not the geometric line view. |
| `engine_v2/pipeline/layout.py:30` | `normalize` projects words to percentage coordinates, retaining source pixel boxes. |
| `engine_v2/pipeline/layout.py:40` | `group_lines` sorts by vertical center, groups against the preceding line's mean center with tolerance 0.6 times the incoming word's height (minimum 0.3 percentage points), then sorts each line by x0. Tall or vertically displaced regions can alter grouping. |
| `engine_v2/extractors/nhis_common.py:110` | `page_lines` applies `group_lines(normalize(result.words, ...))` identically to all providers. |
| `engine_v2/tools/batch_assess.py:405` | Batch measurement renders every PDF page at 300 dpi for OCR and separately builds PyMuPDF text-layer reference words. Unlike ordinary `_load_pages`, this deliberately OCRs text-layer PDFs as well. |
| `engine_v2/tools/batch_assess.py:454` | `_recognize` invokes the original provider callable; its Apple bridge supplies an in-memory image instead of the normal temporary PNG. |
| `engine_v2/tools/batch_assess.py:538` | `_engine` uses a deep-copied text reference or provider words and then calls the shared extraction/conversion path. |
| `engine_v2/tools/documentai_corpus_v2.py:90` | Synthetic v2 reference words also originate from `get_text("words", sort=True)`; transformation mapping retains enclosing boxes (`:102`). |

Ordinary runtime preprocessing can choose text-layer, embedded-image, or rendered-page inputs (`engine_v2/pipeline/preprocess.py:83`). Its text-layer threshold is 50 characters (`:25`); `_load_pages` bypasses the requested OCR engine when text-layer input is selected (`engine_v2/engine.py:179`). Therefore a future three-engine diagnostic must deliberately distinguish forced comparison rendering from ordinary runtime routing.

### Two payment readers, not one uniform table parser

`engine_v2/extractors/nhis_payment.py:346` first calls `nhis_payment_gov.recognizes`. A positive match selects the bounded eight-component government reader; a negative match falls back to the legacy reader. Input fragmentation can therefore change the algorithm before table validation begins.

#### Government reader

1. **Recognition has word-level month/header prerequisites.** `nhis_payment_gov.py:24` checks title plus either document-number or information-grid evidence, computes component header top, then looks for individual words matching `MONTH.fullmatch(squash(word.text))`. `MONTH` is `(0?[1-9]|1[0-2])월` (`:16`). `"1"` and `"월"` in separate words do not satisfy this test. Header recognition requires at least three occurrences each of 보수외 and 소득월액 in reconstructed header clusters (`:33`–`:41`).
2. **Header fragments are expected and reconstructed.** `_header_clusters` (`:121`) sorts words by x0 and merges horizontally overlapping/nearby regions using half a median glyph width. `_header_columns` (`:134`) requires exactly the expected number of clusters and their complete text in order. Each cluster is itself regrouped into lines at tolerance .25 before its text is concatenated. `HEADERS` (`:19`) means nine ordered clusters: month plus four billed and four paid components. `GROUPS` requires exactly two group clusters. Thus this reader does not require each header to arrive as one observation or a whole line.
3. **Header bands must be geometrically separable.** `_monthly_table` (`:161`) selects months only below `metadata_bottom`; group words must lie between metadata and the first month and above component headers. Groups are tested before component headings (`:170`–`:191`). Expanded/crossing boxes can hide or join evidence even if character text is correct.
4. **All 12 months must be single-word anchors in order.** `:165` and `:178` require month-word sequence `[1, ..., 12]`. The first month also establishes the header/body boundary. A missing/duplicated/split month can invalidate both row evidence and header search.
5. **Columns come from persistent empty body corridors.** `nhis_forms.py:195` merges all occupied body x intervals, finds empty corridors between ordered header centers, rejects missing/ambiguous corridors and requires monotonic boundaries. Payment opts into optional columns `(3,4,7,8)` and half-glyph minimum gap (`nhis_payment_gov.py:194`). A wide region spanning multiple amount cells removes the needed gap.
6. **Each complete word must fit within one cell.** `nhis_forms.py:268` rejects a word unless its entire x interval belongs to exactly one column. It does not split a cross-column region into its component values.
7. **Rows use nearest-month geometry.** `nhis_payment_gov.py:201` computes minimum month spacing, assigns body words to nearest month centers and rejects words farther than .45 of row pitch. Column cells must preserve the month anchor, required values, numeric grammar and all eight column sums (`:217`–`:264`).
8. **Metadata can suppress monthly output independently.** Query-period evidence must come from one pre-table row with a complete period and only optional unit residue (`:320`–`:338`). Monthly fields and 고지월 are emitted only if there are 12 values and a parsed year (`:374`–`:389`). Thus a correct body can still lose these fields when period/metadata parsing fails.

#### Legacy reader

1. `nhis_common.label_hits` (`nhis_common.py:116`) concatenates whitespace-stripped words within a geometric line and maps matched characters back to complete source words. It also supports exact two-fragment vertical labels separated by one or two reconstructed lines (`:131`). It neither splits a source word nor fabricates narrower character boxes.
2. `_month_header` (`nhis_payment.py:104`) accepts a label only when the complete selected source words concatenate exactly to that label. A merged source word containing both 月 header and neighboring headings can therefore be rejected even when substring search located the label.
3. `_header_block` (`:119`) expands around the month header using recognized table labels/fragments until body month evidence or unrelated text. `_header_x` (`:150`) derives column positions from whole matched source-word boxes. A label-plus-value or multi-header source region makes its center broader than the printed label's true center.
4. `_extract_monthly` (`:168`) reconstructs page lines and skips a page completely if no month-header index is found (`:210`–`:214`). It starts below the last detected header and stops at confirmation/issuer or sum rows. These choices can lose all monthly rows before amount selection.
5. Legacy month recognition (`:244`) scans the whole reconstructed line for full year-month or compact year-month; month-only labels require `period_start` from `PERIOD_RE` over `OcrResult.text` (`:195` and `:248`). Unlike the government reader, it can find a month after number/suffix splitting when their joined line text is compatible.
6. `_money_words` (`:57`) joins up to four consecutive source words into numeric candidates; `_closest_amount` (`:164`) selects by distance to header-derived x positions. This is a limited numeric-fragment recovery path, not general cell reconstruction. Merged month-plus-amount or multiple-amount source words can fail full numeric matching. Health/paid disambiguation can also refuse the same closest candidate (`:285`–`:292`).
7. Legacy emits 고지월 from observed month rows separately from successful amount extraction (`:430`–`:440`). Missing monthly amount fields and missing 고지월 do not have one identical cause.

### The MISSING_BILLING_MONTHS code is not a precise extractor diagnosis

`demo/backend/rules/doc_check.py:395` primarily reads independent `고지월검증자료`, not just whether the `고지월` field exists. An unreadable, uncertain or conflicting period generates that code with NEEDS_REVIEW (`:399`–`:419`); independently observed range or certain billed-amount omissions can generate it with stronger evidence (`:420`–`:439`).

`engine_v2/extractors/payment_period.py:36` collects separate period/row evidence. It finds table top using exact whole-word table labels (`:62`), parses bounded pre-table period rows and requires confidence .85 (`:66`–`:84`). Row evidence depends on the first word being a valid month in the leftmost 25% of the page (`:90`–`:105`). Thus the measured code cannot, by itself, prove a table-header failure. Period tokenization, confidence, period/body contradictions, genuine query-range omissions, and bounded zero/blank evidence are competing explanations. A text layer removes OCR recognition error but still leaves tokenization, geometry, reader selection and period parsing.

### Synthetic evidence gathered without editing tests

Ran the unchanged focused suites with:

```text
.venv/bin/python -B -m pytest engine_v2/tests/test_p2_payment.py engine_v2/tests/test_p2_payment_headers.py -q -p no:cacheprovider
63 passed, 5 warnings in 4.07s
```

Warnings were existing PyMuPDF/SWIG deprecations. This is focused research validation, not the final four-group regression gate.

Existing tests provide direct counterevidence to a line-only assumption:

- `engine_v2/tests/test_p2_payment_headers.py:27`: horizontal glyph splitting and vertical splitting of group/component headings retain all eight columns.
- `engine_v2/tests/test_p2_payment_headers.py:75`: group headings represented by four vertical glyphs still pass.
- `engine_v2/tests/test_p2_payment.py:113`: fragmented metadata labels and issue dates still produce a complete form.
- `engine_v2/tests/test_p2_payment.py:130`: split amount words remain within their observed column and pass.

Additional one-off **in-memory** probes used only `p2_payment_samples.payment()` and the existing coordinate helper. They printed flags and validation names, no source values, and created no fixture/test files:

| Synthetic variant | Selected reader | 고지월 | 월별고지금액 | Observed failure |
|---|---|---|---|---|
| Unchanged authored region cells | government_payment | present | present | none; complete structure |
| Split each month number and 월 suffix into neighboring source words | legacy | present | present | monthly_total_matches |
| Merge every reconstructed header-band line into one source word/box | legacy | absent | absent | monthly_rows_found, monthly_amounts_numeric, months_continuous |
| Split header-band words into glyph boxes | legacy | present | present | no legacy validation failures |

These probes show both reader-routing sensitivity and that whole-line merging is not generally beneficial. Their coordinates are authored synthetic layouts; they do not reproduce or identify any measured real-document case.

## Fixed payment-form label vocabulary evidence

The approved implementation uses only the narrower **28 module-constant labels** listed completely in design.md; function-local literals and fixture-derived variants below are research evidence, not dump exceptions.

This section inventories **code-owned literal labels** for an independently reviewed exact-whole-word dump allowlist. It is not a value allowlist. Compare the original entire word string exactly; do not squash/trim/casefold for permission, preserve a substring, infer a label from a value, or use broad regional/name exceptions. A source word that contains a fixed label plus any value must be masked in full. A source token that differs by spacing is also masked unless that exact spelling is explicitly listed.

| Source anchor | Literal labels / fragments consumed by the payment path |
|---|---|
| `nhis_payment.py:23`–`:29` | `장기요양보험료`, `장기요양`, `노인장기요양`, `건강보험료`, `건강보험`, `보수외소득월액(건강)`, `보수외소득월액건강`, `보수외건강`, `년월`, `월별`, `보험료월`, `납부월`, `납부년월`, `청구월`, `보험료연월`, `고지금액`, `고지보험료`, `납부금액`, `납부보험료`, `실납부`, `고지`, `금액`, `납부`, `보험료`, `건강`, `년`, `월` |
| `nhis_payment_gov.py:18`–`:21`, `:140` | `건강보험료`, `장기요양보험료`, `보수외소득월액(건강)`, `보수외소득월액(요양)`, `월별`, `년월`, `월`, `고지금액`, `납부금액` |
| `nhis_payment_gov.py:27`, `:287`–`:345` | `문서확인번호`, `가입자성명`, `생년월일`, `사업장명칭`, `납부자번호`, `납부내역`, `단위`, `원`, `납부총액`, `용도구분`; `사업장명칭`/`납부자번호` also gate recognition |
| `nhis_payment_gov.py:182`, `nhis_payment.py:218`–`:243` | `합계`, `납부총액`, `연말정산`, `확인합니다`, `국민건강보험공단` (some are section/end anchors rather than form item headings) |
| `nhis_common.py:153`, `:179`, `:215`, `:239` | `성명`, `주민등록번호`, `생년월일`, `발급일`, `발급일자`, `발행일`, `출력일` |
| `payment_period.py:26`, `:63`, `:70` | `조회기간`, `납부내역`, `단위`, `원`, plus the table headings already listed |
| `nhis_forms.py:30`, `:39` | `확인합니다`, `국민건강보험공단`; standalone issuer anchor can include `이사장` (the regular expression also permits `이사`) |

Component fragment spellings such as `보수외`, `소득월액`, `(건강)`, `(요양)` are consumed through reconstruction against full component labels (`nhis_payment_gov.py:115`–`:145`) and are explicitly used in the unchanged header tests (`test_p2_payment_headers.py:28`–`:32`). They should be separately reviewed and enumerated if retained; do not automatically allow every substring of a full label. Likewise title literals are detection evidence, not automatically item-name exceptions (`nhis_payment_gov.py:26`, `nhis_payment.py:361`). The stable dump vocabulary must state exactly which of these code-owned headings/fragments/anchors it includes. Do not include values such as names, workplaces, document numbers, dates, purposes, 가입구분 values, or arbitrary Korean words simply because they appeared in a fixture.

## Privacy and evidence limits

- `OcrResult.__post_init__` calls `mask_words` (`pipeline/ocr/__init__.py:37`), and both own and Apple adapters already call it before returning (`own.py:136`, `ocr/__init__.py:78`). Text-layer words are masked upon construction of their result (`engine.py:193`).
- This existing resident-number boundary replaces the final six digits with stars while retaining source text length, word order and boxes (`pipeline/privacy.py:31` and `:88`). A diagnostic that consumes extractor-facing words therefore sees stars for those digits. Its subsequent numeric→9 mapping cannot recover their original numeric character type; **keep the stars and disclose this intentional upstream limitation**. Do not bypass the production redaction boundary or retain a raw pre-mask duplicate.
- Confidence affects period certainty and zero/blank certainty; a structure dump that exports no confidence can establish token/geometry differences but cannot fully explain confidence-only findings. No confidence values were gathered from real documents.
- Repeated generic masks cannot prove which label occurred inside a larger source word. Exact-label-only exceptions intentionally lose embedded-label text. Structural dumps can establish region width/order and tokenization; a missing masked label is not proof that the original source lacked it.
- Provider observations may vary with native OCR/runtime versions. Local adapters confirm representation, but do not prove a universal Apple line/own region partition for all documents. No native OCR was run during this research.

## Related specs

- `.trellis/spec/backend/document-form-contracts.md`: bounded payment cells, column sums, fragmented heading comparison, period/identity and redaction boundaries.
- `.trellis/spec/backend/batch-assess.md`: forced OCR versus text references, value-free measurement and synthetic-only verification.
- `.trellis/spec/backend/verify-cases.md`: private location policy, fixed output vocabulary and safe error reporting.

## Caveats / not found

No private structural dumps were available or used. The 275-case provider-rate gap, 111 text-layer missing-month outcomes and 58-field synthetic aggregate difference were supplied by the user and were not independently reproduced here. A causal breakdown by failing validation, form kind or token shape remains deferred to stage 2 after user-provided value-masked evidence. No extractor, OCR, assessment runtime or existing test was changed.
