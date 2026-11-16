# Stage 2-1 routing conditions and input contracts

Prepared on 2026-11-15 from source inspection and user-provided numeric observations. Implementation was approved on 2026-11-15.

## User-provided observations

The operator measured 120 text-layer payment pages. Reference routes were LEGACY 120 / GOVERNMENT 0. Own routes were LEGACY 0 / GOVERNMENT 120. Apple routes were LEGACY 118 / GOVERNMENT 2.

| Engine | Field | OK | ROUTE_MISMATCH |
| --- | --- | ---: | ---: |
| own | MEMBERSHIP | 0 | 120 |
| own | BILLING_MONTH | 1 | 119 |
| own | ISSUE_DATE | 86 | 34 |
| applevision | MEMBERSHIP | 118 | 2 |
| applevision | BILLING_MONTH | 118 | 2 |
| applevision | ISSUE_DATE | 119 | 1 |

All other reported failure codes were zero. These are supplied aggregate observations. The underlying documents and output directory have received zero agent accesses. The route mismatch accounts for the reported failed field comparisons. Which predicate differs remains unmeasured. Content-independent routing across arbitrary inputs cannot be established from these two corpus aggregates.

## Dispatch chain

| Source and function | Selection behavior | Inputs |
| --- | --- | --- |
| `engine_v2/tools/ocr_baseline_runtime.py`, `extract` | Calls `_read_pages` with normalized pairs and a neutral memory-only path | PageImage, OcrWord copies |
| `engine_v2/tools/ocr_baseline_fields.py`, `normalize_words` / `prepare_pairs` | Deep-copy, NFKC, masking, OcrResult construction | Text and confidence, preserved pixel bounds |
| `demo/backend/ocr/pdftext.py`, `classify_with_evidence` / `classify_pages_with_evidence` | Ordered document keyword selection after whitespace removal. Payment keywords are 보험료납부확인서 and 건강보험료납부확인. Other document keywords can win earlier. Coordinate fallbacks apply after keyword classification fails. | OcrResult.text, then page geometry for unrelated fallback families |
| `engine_v2/tools/batch_assess.py`, `_read_pages` | Selects nhis_payment for NHIS_PAYMENT and calls LocalOcr's supported-form path | Classified document kind and prepared pairs |
| `demo/backend/ocr/localocr.py`, `_from_supported_form` / `engine_v2/extractors/attached_pages.py`, `extract_form` | Delegates to extractor after attachment partitioning. A single diagnostic page is returned unchanged by partition. | The same prepared page/word pairs |
| `engine_v2/extractors/nhis_payment.py`, `extract` | Calls `nhis_payment_gov.recognizes`. True delegates to government extract. False continues into the legacy reader. | Exact extraction pairs |
| `engine_v2/tools/own_adapter_diag_evidence.py`, `extract_with_form` | Observes actual calls. Government result form_kind becomes GOVERNMENT. Payment entry returning another form_kind becomes LEGACY. Absence of a payment extractor call becomes OTHER. Failed extraction has a null route. | Delegated extraction result and call observations |

LEGACY is the false-government fallback after payment dispatch. Its later title validation accepts 보험료납부확인 or 건강보험료납부확인. That validation does not select the government/legacy branch. OTHER represents the absence of payment extraction, including another classified document or a generic/unclassified path. It has no independent payment-format predicate.

## Original government predicate

The formula is `GOV_TITLE and (GOV_NUMBER_GATE or INFO_GRID_GATE) and HEADER_BOSUOE_GE3 and HEADER_INCOME_GE3`.

| Proposed condition code | Existing expression or observation | Input dependency |
| --- | --- | --- |
| PAYMENT_DISPATCH_CALLED | Actual nhis_payment.extract entry | Document classification and call observation |
| GOV_TITLE | 보험료납부확인서 occurs in whitespace-squashed OcrResult.text | NFKC/masked text, 15-pixel text ordering |
| DOCUMENT_NUMBER_LABEL | 문서확인번호 occurs in the same text | Text |
| DOCUMENT_NUMBER_PATTERN | DOCUMENT_NUMBER.search(normalize_format_text(text)) succeeds | Whitespace removal, permitted dash mapping, digit grammar 4/4/4/4–5 |
| GOV_NUMBER_GATE | DOCUMENT_NUMBER_LABEL and DOCUMENT_NUMBER_PATTERN | Both text predicates |
| PAYER_NUMBER_LABEL | 납부자번호 occurs | Text |
| WORKPLACE_LABEL | 사업장명칭 occurs | Text |
| INFO_GRID_GATE | PAYER_NUMBER_LABEL and WORKPLACE_LABEL | Text, despite the name the predicate uses no grid coordinates |
| COMPONENT_TOP_FOUND | Initial _component_top(words) is finite | Each normalized box text must be a substring of a component label, while excluded from group labels |
| FIRST_MONTH_FOUND | At least one lower box full-matches MONTH after squash | Initial component top, box y0, complete token grammar (0?[1-9] or 1[0-2])월 |
| HEADER_COMPONENT_TOP_FOUND | _component_top on the candidate header band is finite | First-month box height, candidate band, component-label text |
| HEADER_BOSUOE_GE3 | Final assembled header_text.count(보수외) >= 3 | Band selection, x clustering, row grouping, text |
| HEADER_INCOME_GE3 | Final assembled header_text.count(소득월액) >= 3 | Same geometry and text |
| GOV_PREDICATE | Original recognizes return value, checked against the decomposed formula | All government gates |
| LEGACY_TITLE | Legacy document-type validation expression in nhis_payment.extract | Whitespace-squashed text, observed separately from route selection |

The initial component labels are 건강보험료, 장기요양보험료, 보수외소득월액(건강), 보수외소득월액(요양). The component-top helper excludes tokens that are substrings of 고지금액 or 납부금액. Thus token segmentation can change the initial vertical boundary even with similar visible text.

For the earliest month below that boundary, candidate header words satisfy `first.y0 - 3 * (first.y1 - first.y0) <= word.y0` and `word.cy < first.y0`. A second component-top computation trims candidates. Horizontal clustering uses half the median per-character box width as its gap allowance. Header strings use group_lines tolerance .25, then whitespace removal. The final gate counts repeated substrings. It does not require eight distinct validated columns at this routing step. The government extractor performs subsequent table validation separately.

## Engine input differences

| Input path | Box unit and height | Coordinate conversion | Whitespace and ordering |
| --- | --- | --- | --- |
| text_layer | PyMuPDF get_text(words) word boxes, confidence 1 | Reference-page rotation matrix, 300/72 scale, top-left pixels | Original word text, then shared NFKC/masking |
| own | One OcrWord for each detected text-region crop with a nonblank CTC result. A crop can cover a text line. Height is the expanded polygon's axis-aligned y extent, which can exceed glyph height. | Detection resizes the long side to at most 1600 with dimensions rounded to multiples of 32. Expanded polygons map back to original top-left pixels. | CTC can emit spaces from its dictionary. No word subdivision follows recognition. Sort uses 15-pixel y buckets and x position. |
| applevision | One OcrWord per ocrmac Vision recognition observation. The installed Vision path forwards result.text and boundingBox without word subdivision. Observation size is provider-dependent. | Bottom-left normalized coordinates become top-left pixel bounds using image width/height | Provider text retains internal spaces, then shared NFKC/masking and OcrResult text ordering |

For all paths, common.page_lines normalizes boxes to page percentages and group_lines uses vertical-center distance <= .6 times the incoming box height, floored at .3 page percentage points. Header regrouping uses .25. OcrResult.text separately uses top-pixel-y buckets of 15 pixels. Shared normalization leaves internal whitespace available. squash removes whitespace during title/label/month/header comparisons. Format normalization maps a fixed set of dash characters for the document-number pattern. Confidence is not a government-route threshold.

The installed ocrmac source was inspected locally to verify observation granularity. Engine or provider source edits are outside this stage.

## Falsifiable hypotheses

| Hypothesis | Code evidence | Expected added aggregate evidence | Synthetic reproduction candidate |
| --- | --- | --- | --- |
| H1 broad header band admits repeated body text in operator legacy pages | Header height is three first-month box heights. Tall expanded own boxes can widen it. The route gate counts two substrings without validating distinct columns. | Own HEADER_HEIGHT_RATIO occupies higher bands, both header counts reach >=3, text/Apple remain below threshold | Larger text boxes, changed row spacing, skew or placement near repeated component labels |
| H2 fused tokens suppress a genuine government signature in the synthetic set | MONTH requires a full box match. _component_top requires each box text to fit inside a component label. | Own FIRST_MONTH_FOUND or a component-top flag is X while reference/Apple is O | Header words or month/amount tokens merged by smaller cell gaps or font/size changes |
| H3 segmentation and x clustering change header string reconstruction | _header_clusters depends on per-character width and x overlap. group_lines tolerance depends on box height. | Header counts diverge while title/metadata gates agree, together with character-per-box and height distributions | Column gaps, stacked header labels, font width and line spacing |
| H4 text gates differ before geometry is considered | Titles/labels use joined text. Document number uses dash-normalized regex. Pixel-bucket ordering may interleave fragments. | GOV_TITLE, document-number gate or INFO_GRID_GATE diverges | Split titles, mixed baseline heights, hyphen forms and tightly spaced metadata |
| H5 raster scale and text density affect own detection | Detection uses a capped/rounded raster size and polygon expansion. Text ordering uses a fixed pixel bucket. | Box-count, height and character-length bands differ across engines | Render resolution, font size, page margins and table density |

These hypotheses predict diagnostic outputs. Changing renderers, OCR adapters or selectors belongs to later approved work. This stage reuses the exact preserved 70-page corpus.
