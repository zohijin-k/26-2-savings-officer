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
