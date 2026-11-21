# Code-path evidence: planning only

Inspected tracked source, synthetic test definitions and guidance only. No real PDFs/images, model weights, existing measurement rows, labels or holdout artifacts were opened. No tests or diagnostics ran during planning.

## Failure mechanism and limits

- `engine_v2/pipeline/layout.py:30,40`: percent coordinates; line grouping uses word-center distance and glyph height with tolerance 0.6. Header boxes can become separate lines. Shared grouping should remain unchanged.
- `engine_v2/extractors/resident_abstract.py:291`: number plus date/holder terms must share one grouped line. This establishes a vulnerability to header splitting, not the real printed format.
- `:345`: a single full report-date token starts a row; otherwise content may append to the preceding entry. Split dates and page-boundary mutation need coverage.
- `:396-425`: no bounds adds a warning; empty-page history tracking requires bounds. `:543` uses parsed ordinal/date checks; `:600` therefore misses an undetected table after eight consistent rows.
- `:568-600`: blank/header-only repeats, content pages, two-up and shared-image metadata have existing independent handling. Preserve it.

## Upstream and verdict paths

- `engine_v2/pipeline/preprocess.py:160` enumerates the PDF's full page count. `_process_pdf_page` selects text layer, embedded image or rendered fallback. No source evidence requires changing this stage.
- `engine_v2/engine.py:173` obtains each page's text/local OCR. `engine_v2/pipeline/ocr/__init__.py:189` preserves page order even with own OCR concurrency. User-supplied counts also indicate both pages were processed.
- `engine_v2/pipeline/ocr/own.py` uses pinned local CPU ONNX assets without automatic downloads; no modification planned.
- `demo/backend/ocr/localocr.py:219,273-305` propagates existing history number/empty-page signals and separately caps global confidence for failed history validations.
- `demo/backend/rules/doc_check.py:399` preserves certain missing/duplicate-page FAIL using independent marker evidence only under narrow confidence conditions. Do not broaden the exception.
- `demo/backend/rules/doc_check.py:997` provides the existing review-only history finding. Final FAIL takes precedence over review.
- `engine_v2/engine.py:82` consumes warnings for review and field confidence for confirmed rule failures. New table-read uncertainty must not globally cap independent identity/date evidence.

## Synthetic resources and commands

- `engine_v2/tests/test_resident_abstract.py`: authored words and page/header/row helpers; `test_p2_resident.py`: scale/skew, numbered notes and ordinal defects. Preserve legacy non-one-start engine-validation expectations.
- `demo/backend/tests/test_resident_history_incomplete.py`: exact existing reason strings are asserted; do not repurpose `EMPTY_PAGE` for undetected tables.
- Existing blank-page, page-confidence, shared-image and two-up tests cover independent protections.
- `engine_v2/extractors/address_dates.py`: independent evidence for definitely absent dates; unread dates/table failure must not become a guessed confirmed omission FAIL.
- `demo/README.md:159`: default scenario DB/storage is temporary. Tracked filenames give 18 modules; never use the destructive live option.
- `engine_v2/docs/documentai-staged-measurement.md`: 410 synthetic pairs at samples=5 and seed=20261113; report paths must be new. Historical results are unnecessary.
- `engine_v2/tools/documentai_staged_report.py:116`: false acceptance is PASS on expected-negative cases; review remains distinct.
- `engine_v2/tools/g1g2_report.py:23,78`: separate presentation/validation sets; G2 denominator 165 and supplementary INS4 25 per set.
- `demo/frontend/package.json`: tsc, oxlint and vite executables are present. No frontend edits planned.

## Workflow

The local skill `.claude/skills/trellis-brainstorm/SKILL.md` requires final planning summary plus explicit approval in a subsequent user message before activation/implementation. The user imposed the same gate. Task creation's session pointer is not `task.py start`; status remains `planning`.

Follow the user's single-task condition inline without spawning agents or changing global Trellis config. Load the curated manifests directly when implementation is approved.

`task.py validate` passed both four-entry manifests. It warned that the existing document-form contract exceeds the automatic injection limit (34869 bytes versus 32768). Inline execution must read that contract directly in bounded sections rather than rely on truncated injection; no configuration change or additional agent is needed.
