# Classification recovery diagnostics

Apply to `engine_v2.tools.classify_recovery_diag` and its tests. The tool explains
why the production upload reader leaves documents unclassified and counts what
candidate rules would change, without changing production behaviour.

## Subcommands

- `crosstab --timing <RUN_A>/rows.jsonl --scan <RUN_SCAN>/results.jsonl` reads two
  existing result files only. Rows are validated with `doc_timing.validate_row` and
  `batch_assess.load_rows`. The join key is `doc_timing.document_key(batch id)`; it
  only matches when both runs used the same root, so zero matches print
  `WARNING ROOT_MISMATCH`. Only `.pdf` batch rows are join candidates (doc_timing
  measures PDFs only); the extension is the only part of a name ever read.
- `run --root <HUB_ROOT> --out <OUT> [--timing rows.jsonl --forms K...] [--limit N]`
  re-reads each PDF once through the unmodified `read_document` chain (own engine,
  external OCR disabled, `batch.guarded()` per document), then runs the doc_timing
  slot rule and `assess_upload` for the verdict. `--out` must not exist.

## Exit and cause codes

- Delegation-only `patch.object` wrappers (arguments, results and exceptions pass
  through) record which LocalOcr branch returned None: route (`_tier2_can_read`),
  `_read_pdf`, `engine._load_pages`, `preprocess`, `ENGINES["own"]`,
  `classify_pages_with_evidence`, `independent_page_markers`, `_generic`, and the
  `LocalOcr.read` / `PdfTextOcr.read` results. Exit codes map to localocr.py lines;
  keep the mapping in `exit_code` in sync when `LocalOcr._read` changes.
- Swallowed exceptions keep only the class name (`[A-Za-z_][A-Za-z0-9_]{0,63}`,
  else OTHER). Never read exception messages.
- Unclassified documents get one cause code (first match): EXCEPTION,
  PREPROCESS_ERROR, FIRST_IMAGE_LATER_TEXT, FEW_CHARS_DISCARD, TEXT_RECLASS_DISCARD,
  HIDDEN_TEXT_LAYER, BACKGROUND_ONLY, OCR_ERROR, OCR_EMPTY, OCR_NO_KEYWORD,
  TEXT_NO_KEYWORD, OTHER. Structure codes come from PyMuPDF image info only
  (covering images, stencil = colorspace 0 or ImageMask, SMask = `has-mask`).
- `scan` re-creates the batch_assess reading (`_inspect` 300 dpi render plus
  `_engine` own) for unclassified documents so each cause shows whether rendering
  would have recovered the type.

## Shadow candidates

- A candidate is installed only inside a second, separate read of the same
  document; the baseline read always runs the production functions. Assert in tests
  that the production function object is restored.
- G1 candidates wrap `pdftext.classify_with_evidence` and may only turn an
  unclassified (`None`) result into INSURANCE_4. A document is re-read only when a
  candidate fires on a classify input that returned None in the baseline read;
  otherwise the deterministic path cannot diverge and the baseline form is reused.
- A per-document OCR memo (sha256 of the PNG plus size) makes shadow reads reuse
  baseline words; it is cleared after every document.

## Outputs

- Screen, `summary.txt` and `run.json`: numbers, O/X and fixed codes only, never
  paths, names, keys, values or exception text. `rows.jsonl` adds the 16-hex key.
  Every row passes `validate_row` (closed code sets) before it is written.
- Classify inputs live in memory for one document only and are never written.
- Tests use synthetic PDFs and a content-aware fake OCR (uniform bitmaps produce no
  words) so each reproduced condition runs in milliseconds; real-engine checks of
  the same conditions belong to the task report, not the unit tests.

## Consent mark and payment table stages (row format 2)

- Format 2 adds `consent`, `c1`, `payment`, `p1` and `shadow_errors`. A failing
  shadow keeps the baseline row and records only the stage name (G1, CONSENT,
  PAYMENT); guard violations still abort the document.
- Consent stages reproduce `admin_consent_scan` step by step (template at 1200 px,
  first page resized to the template, ink ratio > 0.035). Never assume the
  production reading works on rasters: a blank 300 dpi raster of the vector form
  already exceeds the ratio in both checkboxes (printed borders render differently),
  so production returns BOTH and the existing scenario only covers vector-identical
  input. The alignment shadow uses phase correlation (translation only) and an
  inner-box variant that excludes `INNER_PT` per side; always report wrong-pass
  counts (blank forms read as a single mark) next to recall.
- Payment stages use the pages and result passed to `nhis_payment.extract` during
  the baseline read (memory only). The first failing validation group gives
  HEADER/COLUMN/ROW/FORMAT/ARITH/TABLE_OK. HEADER_BAND_CUT means the government
  form fails component headers but passes with the largest P1 margin.
- P1 wraps only the GROUPS call of `nhis_payment_gov._header_columns` and returns
  copies of the group words with `y1 - margin`, moving only `group_bottom`. Other
  routes never call it, so their P1 result is the baseline. C1 patches
  `doc_check.ESSENTIAL_FIELD_UNREADABLE_CODES` without the two consent codes for a
  re-assessment of a deep copy of the baseline reading. Tests assert both
  production objects are restored.

## Run comparison, ARITH causes and quality/member-type shadows (row format 3)

- `compare --before <RUN_1>/rows.jsonl --after <RUN_2>/rows.jsonl` joins two existing
  doc_timing runs by key (first measured repeat per document) and prints decision,
  form and tier transitions, per-form changed counts and per-reason document counts.
  Both runs must use the same root (`WARNING ROOT_MISMATCH` otherwise). Rows without
  `reasons` (doc_timing format 1) count as having no reasons.
- D1 `arith_*` keys are filled only for LEGACY payment rows whose first failing stage
  is ARITH. They recompute `nhis_payment._extract_monthly` and name the gap between
  the printed total and the month sum (+ settlement) with the first match of
  MONTHS_MISSING, DIFF_EQ_SETTLE, DIFF_EQ_CARE, DIFF_EQ_ONE_MONTH, SUM_GT_TOTAL,
  SUM_LT_TOTAL. Amounts never leave the function.
- C2 patches `doc_check.engine_image_quality_status` so FAIL becomes NEEDS_REVIEW and
  re-assesses a deep copy of the baseline reading, only for rows whose baseline
  LOW_IMAGE_QUALITY severity is FAIL.
- A2 re-reads (`_shadow_read`) only documents with a known form, a
  REQUIRED_FIELD_UNREADABLE finding and an original quality below 0.6, with
  `preprocess` replaced in both `engine_v2.pipeline.preprocess` and `engine_v2.engine`
  by a 300 dpi render of every page. The final image quality is still measured from
  the original file, so LOW_IMAGE_QUALITY can only change severity, not disappear by
  rendering.
- A4 recomputes 가입구분 for payment rows from the pages passed to the extractor:
  only lines above the monthly table header (or the confirmation sentence), never
  lines starting with ※; both or neither of 직장가입/지역가입 leaves it empty. The
  upload verdict does not read 가입구분 (it is an application-level income fact), so
  A4 reports value transitions with the unchanged upload decision.
