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
- Row format 3 also adds `recovery` (code, outcome) for the production LocalOcr 300 dpi
  render retry (`localocr.RETRY_CODES`, reason `RENDER_RETRY:<code>` in `fallback_reason`).
  The retry is wrapped so its own reading is excluded from the 1st-path trace
  (`in_local` off); exit and cause codes still describe where the 1st path gave up, and
  the "X" summary lines cover documents whose 1st path gave up (still X or recovered),
  with `XFINAL` and `RECOVERY` lines for the outcome.
- Row keys `s1`–`s4` (format 3 additions): S1 counts header-band page markers per sheet
  (2-up printing, markers >= `S1_SPREAD` apart, one document number) and scores the merged
  set; S2 re-reads sheets with fewer than `S2_MIN_HANGUL` Hangul characters (or of
  unclassified documents) at 90/180/270 degrees and keeps a rotation only with
  `S2_RATIO`/`S2_MIN_GAIN`/`S2_CONF_FLOOR`, recording extra seconds; S3 classifies where the
  final 발급일 appears (LABEL, LABEL_TEXT, HEADER_BAND, CONFIRM_BAND, OUTPUT_LABEL,
  LABEL_LEFT, OTHER, NONE) and counts '열람용'; S4 counts absence FAILs with unreadable or
  low-confidence evidence and whether the address table header was seen. Converter pages,
  resident pages and preprocess images are captured in memory for one document only.
- Row format 4 adds `early` and `billing` (D6, no values): for a DOCUMENT_ISSUED_TOO_EARLY
  FAIL, the S3 source class of the 발급일 (`NA` outside the issue-dated forms) and the gap
  before the slot cutoff (`D1_30`, `D31_365`, `D366P`, `FUTURE` after today, `NA`); for a
  MISSING_BILLING_MONTHS FAIL, the number of months in 월별고지금액 (`M0`, `M1_2`, `M3_5`,
  `M6_11`, `M12P`, `NA`). Summary lines `D6_EARLY` and `D6_BILLING`.
- Row format 5 adds `history` (D8) for RESIDENT_ABSTRACT rows: the production ordinal state
  recomputed from the pages the extractor read (`CONTIGUOUS`, `GAP` missing/duplicate/not
  starting at 1, `UNREADABLE` an entry without an ordinal, `NA` no entries or no OCR pages)
  and `empty_page` (a counted page whose table header was found but yielded no row). Summary
  lines `D8` and `D8_DECISION`.
- Row format 6 adds `g4` for NHIS_PAYMENT rows: the 11-19 고지금액 guard reasons carried by the
  stored reading (`zero` ZERO_AMOUNT, `ratio` CARE_RATIO, `header` CARE / UNCERTAIN / BOTH / X,
  `larger` LARGER_HEALTH) and the table layout (`GOV`, `COMBINED`, `NO_CHARGE_HEADER`, `NA`, or
  `SINGLE_`/`GROUP_` × `HEALTH`/`SHORT`/`FUSED`/`MISSING` from `nhis_payment.amount_layout`).
  Summary lines `G4`, `G4_HEADER`, `G4_LAYOUT` and `G4_DECISION`.
- S3 `issue_source` locates dates with `nhis_common.dates_in_line` plus `_line_dates`, which
  also reads a date immediately followed by HH:MM ("2026-03-0310:20"). Before this, a 4대보험
  발급일시 value was reported as OTHER although the extractor took it from the 발급일시 label
  cell (synthetic originals 5/5 OTHER, now LABEL).
- Row format 7 adds `d10` for documents whose verdict carries PAGES_DUPLICATED: the production
  per-page blank rule of `resident_abstract.extract` is replayed with the same calls on the pages
  the extractor read (`consistent` X when the replay's left-out count differs from the
  extractor's `blank_pages`). Per page: OCR boxes, Hangul/Latin/digit counts, marker read (O/X),
  header-band n/m count (`nm`), marker repeated on another page, `content` (TABLE_ROWS,
  TABLE_CHARS, TABLE_ONLY, BODY_CHARS, NO_CONTENT), body characters, counted (O/X) and `keep`
  (CONTENT, BLANK_/TABLE_ONLY_ × NEW_MARKER/NO_MARKER/DUP_MARKER, ALL_BLANK), ink share of the OCR
  input image and of a 72 dpi render of the page as displayed (grey < 128; -1 none), image pixel
  size and dpi, page source (TEXT_LAYER, EMBEDDED, RENDER, UPLOAD), text-layer characters, image
  placements, main image xref shared with another page, and the first earlier page with the same
  image bytes / same reading text (-1 none). Document `path`: MARKER_DUP (the only production
  PAGES_DUPLICATED route: repeated counted markers), IMAGE_SAME, OTHER. Summary lines `D10`,
  `D10_DOC` and `D10_PAGE` (document ordinal and page number, never a key).
- Row format 9 adds `d11` for every processed document (11-19): page-image source of the pages of
  the last production `preprocess`. `embedded` counts EMBEDDED pages (OCR input is the embedded main
  image, not the page as displayed); per document O/X: `shared` (main image xref, production
  `PageImage.image_xref`, is another page's too), `hidden` (72 dpi render ink < .002 while OCR-input
  ink > .01: an image that does not show), `ratio` (OCR-input ink / render ink >= 3 or < 1/3); `bins`
  counts EMBEDDED pages per ratio bin (R_LT033, R033_1, R1_3, R3P, NA = no image or render ink
  < .002), summing to `embedded`. Ink is grey < 128, as D10. D10 now also runs for PAGE_IMAGE_SHARED
  verdicts. Summary lines `D11` (documents, embedded documents, shared, hidden, ratio, any),
  `D11_FORM_DECISION` (same counts per form x decision, embedded documents only) and `D11_RATIO`
  (pages per bin). Cost: one 72 dpi grey render and one decode of the OCR input per EMBEDDED page.
- Row format 8 adds `t3` for NHIS_PAYMENT rows (shadow, production unchanged): the held T3 change
  (the legacy 합계 row read from the 건강보험료 column the months come from, not the 고지금액 group
  centre) is applied in memory by exact source substitution of `nhis_payment._extract_monthly_detail`
  (`T3_SOURCE`; a source that no longer matches raises `T3_SOURCE_CHANGED`, recorded as a shadow
  error, never guessed). `layout` is `amount_layout` (GOV rows: before/after `NA`); `before`/`after`
  are MATCH, MISMATCH or NO_TOTAL of `monthly_total_matches` on the production pages; `decision` is
  the verdict of a second read with the change installed (OCR reused). Summary lines `T3`
  (match counts, newly matching, lost, PASS before/after), `T3_DECISION`, `T3_TOTAL`, `T3_LAYOUT`.
- Row format 10 (11-19): T3 is applied in production. `t3_applied()` reads the production source:
  every `T3_SOURCE` new text present → applied (`t3.applied` O: `after` = `before`, `decision` = the
  production verdict, no second read, no shadow error); every old text present and no new text →
  the in-memory shadow as before (`applied` X); anything else → `T3_SOURCE_CHANGED`. GOV/no-page
  rows: `applied` NA. The `T3` summary line ends with `applied` (O, X, NA, or MIXED). Tests keep
  the shadow path on a synthetic pre-T3 source (the substitution reversed). `payment.component` is
  the production `구성머리글불완전사유` (FRAGMENT, GAP, BOTH; NONE when absent or not one of these);
  summary `PAYMENT_COMPONENT reason decision n`.
