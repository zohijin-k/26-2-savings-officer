# Research: engine and input privacy boundaries

- **Query**: Reuse own/AppleVision, content classification, extraction and upload assessment without production edits or value persistence.
- **Scope**: Internal repository source and repository-local dependency source only; no document inputs, external files, dependency imports or inference were inspected. `.venv`, package directories and inspected files were checked to be non-symlink targets contained in the repository before reading.
- **Date**: 2026-11-13
- **Task context**: The parent supplied this task directory explicitly. The child session's `task.py current --source` reports no active task because active pointers are session scoped.

## Findings

### Files found

| Code path | Relevant boundary |
| --- | --- |
| `engine_v2/pipeline/ocr/__init__.py:49` | `_with_tempfile` persists PNG bytes before invoking an engine and then deletes them. |
| `engine_v2/pipeline/ocr/__init__.py:64` | AppleVision always uses that temporary-file helper and converts normalized lower-left boxes to top-left pixel boxes. |
| `engine_v2/pipeline/ocr/own.py:38` | Cached own CPU sessions verify pinned local model files; no automatic download. |
| `engine_v2/pipeline/ocr/own.py:114` | Own recognizes PNG bytes in memory using OpenCV/ONNX. |
| `demo/backend/ocr/localocr.py:653` | `LocalOcr.read` deliberately ignores expected upload type. |
| `demo/backend/ocr/localocr.py:665` | Local reader accepts only PDF/JPG/JPEG/PNG names. |
| `demo/backend/ocr/localocr.py:759` | Raster pages go through selected OCR, then existing content classifier and per-type extraction. |
| `demo/backend/tools/verify_upload.py:34` | Audit guard blocks filesystem writes, subprocesses and SQLite connections. |
| `engine_v2/tools/private_bench.py:27` | Quiet boundary discards Python and native stdout/stderr; buffers are flushed before restore. |
| `engine_v2/tools/documentai_bench.py:134` | Existing benchmark scopes temporary function/environment substitutions around unchanged local reader and shared upload assessment. |

### AppleVision and no persistent content

The existing AppleVision adapter cannot execute unchanged inside `quiet_assessment`: its temporary PNG write is rejected by the audit guard. Removing that guard would violate the requested no-content-on-disk requirement. Repository-wide searches found no direct `Vision`/`VNRecognizeTextRequest`, NSData/CGImage, or memory-only `ocrmac` adapter.

A concrete tool-scoped memory adapter route is confirmed from the repository-local installed `ocrmac` 1.0.1 source. `.venv/lib/python3.14/site-packages/ocrmac/ocrmac.py:290-309` accepts a `PIL.Image.Image`; its Vision helper also accepts that object (:121-124), encodes to `io.BytesIO` (:70-74), and passes bytes to `Vision.VNImageRequestHandler.alloc().initWithData_options_` (:156-158). The tool can decode PNG bytes with `Image.open(BytesIO(png))`, pass the image to `ocrmac.OCR(image, language_preference=["ko-KR", "en-US"]).recognize()`, and retain existing normalized lower-left to top-left pixel box conversion. This is invocation plumbing in the tool, without changing production source or writing a temporary raster. No dependency was imported and no inference was run, so native capability/available languages still need a synthetic probe inside the write guard. Fixed skip outcomes remain necessary for absent platform/package/language capability; do not skip an otherwise usable installation merely because the production wrapper uses a tempfile.

`run_ocr` itself catches dependency exceptions and puts message text into transient `OcrResult.error` (`engine_v2/pipeline/ocr/__init__.py:158-168`). Never record this string. A scoped callable wrapper can observe exception class names before that catch; it must discard messages and delegate the original callable unchanged.

### Formats, pages and tool-only adaptation

`preprocess` supports PDF and a still-image suffix set containing HEIC, but excludes GIF/JFIF (`engine_v2/pipeline/preprocess.py:137-158`). Image preprocessing returns one `PageImage`; there is no GIF frame enumeration or HEIF plugin setup in repository code. `LocalOcr` rejects HEIC/GIF/JFIF before preprocessing (`demo/backend/ocr/localocr.py:665`). Merely adding allowed extensions to directory walking would therefore silently yield no local extraction.

Pillow is an existing dependency (`engine_v2/requirements.txt:4`). Existing image helpers read sizes/metadata with Pillow, but only for JPG/JPEG/PNG (`demo/backend/ocr/file_evidence.py:21-28`). A tool-local decoder can expose frames as existing `PageImage` objects and use an explicitly scoped reader entry/input adapter; no converted image should be saved to disk. GIF frame-count semantics and HEIC decoder capability need explicit synthetic coverage. The local Pillow plugin list contains GIF and JPEG plugins but no HEIF/HEIC plugin (`.venv/lib/python3.14/site-packages/PIL/__init__.py:27-75`); the repository-local site-packages inventory has no `pillow_heif`/HEIC package, and no HEIF requirement or registration exists in project sources/manifests. This does not prove PyMuPDF's native HEIC decoder is unavailable; its production suffix route still needs a synthetic decode capability test. Unsupported/corrupt decodes must be attempted and recorded as fixed open/capability failures, not silently counted as ignored extensions.

PDF production preprocessing uses a 50-character threshold per page (`engine_v2/pipeline/preprocess.py:25,88-93`), whereas the local reader routes text PDFs after any non-whitespace text on their first page (`demo/backend/ocr/localocr.py:637-645`). Record page coverage explicitly, keep eligibility for a full-text reference distinct from merely nonempty text, and force every own/Apple reference comparison page through memory raster OCR. `private_bench.raster_pages` already renders every PDF page at 300 DPI in memory (`engine_v2/tools/private_bench.py:63-77`).

### Classification, extraction and comparison

`pdftext.classify_pages_with_evidence` first applies existing content keywords and then coordinate title fallbacks (`demo/backend/ocr/pdftext.py:103-130`). The normal local raster path uses it before choosing the extractor (`demo/backend/ocr/localocr.py:766-835`). Do not select extraction from an expected upload slot.

`documentai_bench.measure` demonstrates temporarily restricting `demo_ocr.CHAIN`, selecting an explicit engine, intercepting preprocess, and observing extractors while still invoking shared `assess_upload` (`engine_v2/tools/documentai_bench.py:134-204`). Its fixed benchmark requirement/date and five-type list are not a complete batch contract. Prefer the normal per-type program requirement mapping elsewhere in the repository for batch assessment; do not import its hard-coded policy as a universal rule.

There is no complete universal positive field-name vocabulary. `documentai_bench.FIELD_NAMES` covers only five benchmark types and omits some production fields (`engine_v2/tools/documentai_bench.py:22-35`). Examples outside that vocabulary include business fields (`engine_v2/extractors/business_registration.py:27`), interview fields (`engine_v2/extractors/interview_confirmation.py:125-154`), resident address history (`engine_v2/extractors/resident_abstract.py:435-510`), and additional payment month fields (`engine_v2/extractors/nhis_payment.py:413-435`). Author a reviewed tool-owned vocabulary from existing fixed extractor keys; arbitrary output keys must not become field names.

The backend field map mixes extracted semantic fields with validations, confidence/evidence objects and warnings (`demo/backend/ocr/localocr.py:126-177,327-402,457-508`). Never serialize that map or include these evidence-only keys in extraction-rate denominators. Observe extractor semantic values in memory, or project a reviewed backend semantic-name list consistently for both engines.

`documentai_bench._semantic_value` parses known JSON semantic fields and excludes insurance geometry/confidence columns (`engine_v2/tools/documentai_bench.py:55-69`). `documentai_staged.canonicalize` provides symmetric field-aware normalization preserving types, list order, leading zeroes and semantic punctuation (`engine_v2/tools/documentai_staged.py:37-91`). Planning must state whether batch O/X is literal typed equality or that existing normalized equality. Missing on both sides must never count as an agreement. Agreement with text layers is a silver reference, not accuracy against independent truth.

## Related specs

- `.trellis/spec/backend/verify-cases.md`: resolved private location policy, positive vocabularies, quiet/read-only assessment, synthetic-only tests.
- `.trellis/spec/backend/documentai-measurement.md`: unchanged production logic, complete page coverage, semantic comparison boundaries and failure denominators.
- `.trellis/spec/backend/quality-guidelines.md`: own local pinned models, no automatic inference downloads, no generated assets staged.

## Caveats / not found

- Memory-only Apple invocation is confirmed by local dependency source, but native execution and supported language availability remain untested; retain capability probes and fixed failure/skip outcomes.
- HEIC decoding capability is not proven; Pillow's installed plugin list and dependency inventory do not provide a HEIF decoder, while the existing PyMuPDF HEIC suffix route remains a synthetic-probe candidate.
- No document input, real path or real filename was inspected or recorded in this artifact.
- No product or production source was changed; no model, OCR or test execution was performed.
