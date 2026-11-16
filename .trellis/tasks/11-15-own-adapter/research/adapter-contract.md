# Adapter and actual extractor contract

This is source-derived evidence. No existing document tree or masked dump was read. The stage-0 baseline uses current HEAD 2b4ab59.

## Actual call path

`ocr_baseline_runtime.extract(page, words, engine)` calls `batch_assess._read_pages` with the neutral virtual PDF path and `ocr_baseline_fields.prepare_pairs`. `_read_pages` classifies using `pdftext.classify_pages_with_evidence`, observes the supported-form extractor without replacing its algorithm, and delegates to `localocr._from_supported_form`. Payment dispatch is `nhis_payment.extract`; its first condition is `nhis_payment_gov.recognizes`, followed by `nhis_payment_gov.extract` for a recognized government form. Reader finalization continues through the original `demo.backend.ocr.read_document` contract. Diagnostic observation and every counterfactual must use this same runtime entry point.

## Eight boundaries

| Boundary | own | Apple Vision | Shared extractor input |
| --- | --- | --- | --- |
| Unit | One OcrWord per nonempty detector crop after CTC decoding | One OcrWord per Vision returned observation | Both are lists of OcrWord, not a guaranteed lexical-word segmentation |
| Coordinates | Detector polygons mapped to clipped top-left input-pixel bounding boxes | Bottom-left normalized Vision boxes converted to top-left input pixels | `layout.normalize` converts pixels to page percentages; original pixel boxes remain evidence |
| Line grouping | No extractor-specific line grouping in adapter | No extractor-specific line grouping in adapter | `group_lines`: center-y distance at most current word height × 0.6; minimum height 0.3 percent |
| Ordering | Adapter sorts by rounded y/15 then x | Preserves returned observation order | OcrResult.text also sorts y/15 then x; layout grouping independently sorts center y and line x |
| Korean whitespace | CTC output includes dictionary spaces as recognized | Returned observation text is retained | `line_text` joins with spaces; `squash` removes whitespace where the specific parser calls it |
| Unicode/punctuation | Recognized text retained except production masking | Recognized text retained except production masking | Baseline deep-copies then NFKC-normalizes and masks both sides; field canonicalization is symmetric, not a recognition correction |
| Confidence | Mean emitted CTC scores for a detected crop | Vision observation confidence | Original values are preserved. Different segmentation changes which confidence spans a field; no adapter repair is applied in stage 1 |
| Rotation | Tall detected crops may rotate 90 degrees before recognition; boxes stay in original input coordinates | Existing Vision invocation and box conversion remain unchanged | Baseline reference coordinates apply PDF rotation; clean uses existing 300-DPI rendering; extraction uses each actual input geometry |

## Payment field semantics

- Legacy membership is derived from squashed body text containing workplace/regional membership spelling, or the actual `사업장\s*명칭` regex branch. A literal membership label is not required. Government payment does not emit this field.
- Legacy billing months come from `_extract_monthly` and its month/header/period/year evidence. Government billing months are emitted only with twelve table rows and a confirmed year. A serialized month list is not a literal source anchor.
- Legacy issue date uses `common.page_headers`/`consensus`, then `_body_issue_date` when appropriate, and checks consistency with printed headers. Government uses `nhis_forms.confirmation_issue_date`, which locates a unique date between the confirmation sentence and issuing organization. A literal issue-date label is not mandatory.
- Shared date syntax uses `DATE_RE`, `COMPACT_DATE_RE` and calendar parsing; numeric-format normalization belongs to its existing parser scope. Diagnostic copies must not change real extraction values or confidence.

Actual engine adapter lists and these parser contracts differ from a lexical-token assumption. This establishes possible diagnostic boundaries, not the cause of a private document's failure. Synthetic and private form equivalence cannot be established without private input access; report **합성·실서류 서식 차이 가능**. Government payment's explicit eight-column reader and legacy's separate table/period reader are a concrete form distinction.

## Existing government-payment dispatch predicates

`nhis_payment.extract` calls `nhis_payment_gov.recognizes` before its legacy reader. The predicate consumes the actual OCR text and normalized word geometry through `nhis_common.page_lines`. Government selection requires all three conditions below.

1. Whitespace-squashed text contains the literal title 보험료납부확인서.
2. Either 문서확인번호 occurs with a format-normalized document number matching four groups of 4/4/4/4–5 digits separated by hyphens, or both 납부자번호 and 사업장명칭 occur.
3. The spatial header band supports the eight-column signature. The reader locates a component-label top, then the first lower word matching a complete month token such as 1월 through 12월. It collects header words whose top lies within three first-month heights above that month and whose center lies above it, then trims at the component-label top. X-coordinate clustering uses half the median glyph width as its gap allowance. Cluster text is assembled with line grouping tolerance .25. The resulting header text must contain 보수외 at least three times and 소득월액 at least three times.

The component labels are 건강보험료, 장기요양보험료, 보수외소득월액(건강), and 보수외소득월액(요양). Group labels 고지금액 and 납부금액 are excluded from the component-top calculation. These literal/number/geometry requirements explain the dispatch boundary. An observed legacy route means the combined recognizes predicate returned false. The aggregate route observation does not identify which conjunct failed on an individual page. This follow-up inspects these existing functions without changing them.
