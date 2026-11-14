# Repository research (source only, no document reads)

## Reusable interfaces

- `engine_v2/tools/batch_assess.py`: `inventory`, `_ids_selection`, `_selection_progress`, `_location`, `_target`, `_open`, `_atomic`, `_append`, `_load`, `_incomplete_tail`, `guarded`, `_memory_bridge`, `_recognize`, `_read_pages`, `_field_values`, `_semantic_field`, `_typed_equal`, `FIELDS`.
- `batch_assess.load_rows`/`validate_row` and run metadata are specific to its own schema; do not apply them to OCR baseline rows by monkeypatching global validators. Reuse lower-level parsing/storage primitives and implement a distinct closed schema.
- `batch_assess.run` binds root/engines and persists complete document rows, skips completed errors and repairs only incomplete final records. `--ids` selection can expand between invocations without invalidating the run. Baseline additionally binds variants/settings and supports a document limit.
- `batch_assess._inspect` renders every page and uses nonempty text coverage. It is unsuitable for this task's existing trusted-threshold/page-filter semantics; implement a tool-only page inspection loop and reuse production threshold constants.
- `batch_assess._read_pages` classifies without an expected slot, dispatches production extractors/conversions, then calls production `read_document` finalization via an in-memory reader. It does not call service assessment. Pass a neutral PDF virtual path because generic extractors may inspect paths. Evaluate one page at a time.

## Eligibility, geometry and masking

- `engine_v2/pipeline/preprocess.py`: `TEXT_LAYER_MIN_CHARS=50`; `_process_pdf_page` uses `mask_rrn(page.get_text('text')).strip()` and its length before selecting the text-layer branch. Do not call the full renderer just to filter pages.
- `demo/backend/ocr/pdftext.py`: `classify_pages_with_evidence` uses text first and supported geometry fallback, with no expected slot. `split_pdf_pages` writes PDFs and MUST NOT be used here.
- `engine_v2/pipeline/layout.py`: `normalize` returns page-percent geometry; `group_lines` uses center distance, tolerance .6 and minimum current-word height .3 percent. Reuse and document its limitations.
- `engine_v2/pipeline/ocr/__init__.py`: engines map has own and Apple production callables. Apple `_with_tempfile` normally writes a raster; reuse the batch PIL/BytesIO bridge. `run_ocr` converts dependency errors into message strings, so use guarded explicit callables and fixed error projection instead.
- `engine_v2/pipeline/ocr/own.py`: ONNX CPU session configuration is intra=2/inter=1; sessions are cached. `_detect`, detector session inference and recognition session inference are observable through delegating wrappers. Never change production model/session settings.
- `privacy.mask_words` mutates word text; own and Apple invoke it before return, and `OcrResult` invokes it again. Raw CER requires a scoped pre-mutation observer; normal masked output must remain unchanged. No privacy bypass or raw persistence.

## Table findings

- No shared generic local page-table-region detector is exposed.
- `resident_abstract._table_bounds` returns a vertical history-table band, not full cell polygons. Reuse only for its supported resident form and label the approximation/coverage.
- Other form-specific helpers (`insurance_4._portal_table_layout`, `nhis_payment_gov._monthly_table`, daily-work adapters) return extraction-specific structures rather than a common complete region. Do not invent page-wide regions or bring in remote table OCR.

## Fields and synthetic references

- Batch field vocabularies exclude evidence/confidence. `_semantic_field` retains meaningful ordered history rows while removing unrelated evidence metadata.
- `documentai_staged.canonicalize` is a different, broader normalization policy. It is not the exact batch semantic equality policy. Keep field-match equality explicit and normalize only the literal-presence diagnostic independently.
- Existing synthetic helpers such as `engine_v2/tests/nhis_form_samples.py:text_pdf` author fictitious text-layer PDFs and can be reused without opening stored samples. Synthetic v2 reports remain the separate independent extractor benchmark.

## Isolation and safety

- `verify_upload.quiet_assessment` combines Python/native quieting with a write/DB guard. `batch_assess.guarded` adds no-network enforcement and detects swallowed attempts. Open output streams and execute persistence only outside this boundary.
- `verify_cases._private_location` requires ignored and untracked output inside a checkout; external runtime output is also supported. Validate atomic siblings and hardlink/symlink aliases as batch does.
- `demo/backend/tests/__init__.py` automatically inspects its samples directory and generates samples only when it finds none. Running requested tests in the original checkout could therefore read existing inputs. Use a tracked-source-only isolated copy and freshly generated samples. Do not inspect/copy ignored corpus or upload trees.

## Planning state

Task and branch creation were approved first; implementation approval subsequently followed, including mandatory NHIS payment region measurement and symmetric field normalization. Task is now in progress, with a separate commit approval still required. Available local helper skill search found no Trellis skill files, so this phase follows the repository workflow directly.
