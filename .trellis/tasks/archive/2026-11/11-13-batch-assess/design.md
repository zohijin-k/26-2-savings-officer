# Batch assessment design — approved with 2026-11-13 refinements

## Boundaries

Add a standalone CLI, new tests and documentation. Production OCR, classifiers, extractors, assessment, verdict and frontend files remain unchanged. Repository investigation and future synthetic work stay inside this checkout; do not inventory existing ignored document/data directories. Create a fresh synthetic sandbox under an already ignored repository-local directory, without adding ignore rules. Examples below are entirely fictitious.

```
python -B -m engine_v2.tools.batch_assess --root FAKE-input --out FAKE-output --engines own applevision
python -B -m engine_v2.tools.batch_assess --summarize --out FAKE-output
```

The fake output must still meet the actual location policy; the example is not a bypass.

## 1. Discovery and storage

Walk deterministically using directory entries, without opening excluded files. The first component below root assigns the group; store a stable first-seen mapping before writing rows. Group 0 owns direct root children. Relative IDs preserve original spelling, case and Unicode. Ignore symlink files/directories for content processing and count them separately, avoiding root escapes and cycles. Hidden paths include a dot-prefixed component; classify excluded entries by extension only. Unsupported/excluded extension strings themselves must be bounded safe tokens: unusual text maps to a fixed OTHER bucket so a crafted extension cannot leak text through metadata. Empty extensions have a fixed NONE bucket.

Proposed artifacts:

- `run.json`: schema/configuration, permitted canonical root path, requested engines, policy/field vocabulary version, immutable original run settings, persistent group mapping and numeric inventory counters. No original/derived content.
- `results.jsonl`: one strict complete document record per completed relative ID, appended immediately.
- Run-level setup/location/resume/output errors are exit-only (2), and interrupts exit 130. No catch-wide error artifact is written: failed validation or lock acquisition must not mutate inputs/results or bypass another writer's lock. Per-file fixed error codes/classes remain in results.jsonl.

Apply `verify_cases._private_location` to resolved directory and every output/atomic sibling. An actual destination inside the repository must be ignored **and** untracked; mere untracked status is insufficient. Outside locations remain a supported operator runtime feature, but development verifies that branch using fake Git roots wholly inside this actual repository. Reject a destination under input root, tracked descendants, output symlinks, and source aliases including hardlinks. Check newly created directories/files before content writes, use restrictive permissions and exclusive/no-follow opens, and keep Git subprocess checks outside the assessment guard.

Record serialization is a positive projection into a closed versioned schema, never a dump of OCR/extractor/assessment objects. Validate loaded rows equally strictly; no unknown metadata can be echoed in summaries.

## 2. Read-only processing pipeline

1. Under the existing `verify_upload.quiet_assessment` boundary, open the original once for inspection: real page count, encryption/open failure and per-page non-whitespace text coverage. Hold content, decoded images and text only in memory.
2. Prepare PDF pages at 300 DPI in memory for both OCR engines, even for text PDFs. Reuse `private_bench.raster_pages`/existing `PageImage` contracts. This prevents text-layer bypass from being mislabeled own OCR. For accepted images, a tool-owned decoder produces equivalent in-memory `PageImage` objects; JPEG/JFIF share decoding, GIF frames are composited/enumerated as pages, HEIC images are enumerated if the installed local decoder supports them. Decode/capability failures remain supported-file failure rows, never ignored-extension counts.
3. Run selected engines explicitly and sequentially. Own delegates the pinned local recognizer. Apple delegates the unchanged production Apple callable, with a scoped replacement of its `_with_tempfile` bridge that invokes the supplied function with `PIL.Image` decoded from `BytesIO` instead of a pathname. Local ocrmac source confirms image input support; original language settings and bbox conversion remain unchanged. Restore scoped patches on success, failure and interrupt. No temporary PNG or OCR subprocess is permitted.
4. Classify each engine's words using `pdftext.classify_pages_with_evidence` before selecting an upload slot. Discard evidence when projecting output. A small tool-side dispatch table calls existing extractor and local-reader conversion callables, preserving `extract_form` attachment scoping and generic `pdftext` readers; do not reproduce extraction, confidence or verdict algorithms. Pass results through the existing `read_document` postprocessing using a single in-memory adapter, with fixture/remote/text fallback absent. This bridge is necessary because the production local-reader extension gate excludes some requested formats.
5. Resolve an existing upload requirement **after** independent own classification. Call `upload_assessment.assess_upload` with the original path, `identity=None`, no identity callback, no DB loaders and an injected reader returning the already computed own result. Do not run OCR a second time for assessment. Preserve original extension for upload-format rules; accepting an extension for batch inspection does not make it an accepted application-upload format.
6. Project only status, reviewed code/severity pairs and field metrics; release private per-file objects before proceeding.

Extend the tool's guard only for the missing local-only network prohibition (e.g. socket connect/name-resolution audit events); reuse the existing filesystem/process/SQLite guard. Guarded dependency imports and capability probes discard all stdout/stderr/native/logging noise. Bytecode is disabled before backend imports and invocation uses `-B`. No dependency/model download or environment-file loading.

### Approved upload-context policy

The CLI has no applicant/program arguments. Use repository-default **double_savings** criteria and canonical requirement builders for its document kinds, assembling only the approved work mappings and paper consent/labor requirements without asserting an applicant's actual category. This is document-level measurement under a fixed policy, not an application verdict. Record the fixed policy ID and actual selected slot in each row/run metadata.

| Classified kind | Proposed requirement source |
| --- | --- |
| Resident abstract / three NHIS types | Default double_savings checklist and criteria |
| INSURANCE_4 | Existing `work_proof`, WorkCategory.EMPLOYEE (직장가입자) |
| BIZ_REG_PROOF | Existing `work_proof`, WorkCategory.BUSINESS (사업소득 사업자) |
| Daily work / farm / fishery and any other undetermined work kind | NOT_ASSESSED, WORK_CATEGORY_UNMAPPED; never infer an unapproved category |
| Labor contract / admin consent | Existing applicable labor/paper-consent requirement |
| Unsupported counterpart (e.g. resident certificate), job-package-only kind or no kind | Preserve detected kind; assessment NOT_ASSESSED with SLOT_UNAVAILABLE / CLASSIFICATION_FAILED |

Do not choose a job subsidy/receipt slot, amount, application date or authenticated identity from names or guesswork. Extending policy to job-package kinds would be a scope decision requiring a reviewed deterministic mapping. The user approved this fixed default and the two work mappings. Never perform multi-document income or work-continuity checks; assess each document independently.

## 3. Field comparisons and denominators

Author a complete, reviewed type-to-semantic-field registry from existing extractor and adapter keys. Reuse canonical raw extractor field values where available; generic readers use an explicit semantic backend-key projection. Keep field aliases stable per type. Do not include validations, geometry, confidence, warnings or evidence objects in presence/agreement metrics. Unknown names are omitted; never serialize arbitrary dependency-derived field names. Mixed semantic/history fields require an explicit reviewed projection that excludes evidence-only keys before comparison.

Presence O means a field was actually produced with a meaningful value; absent/null/empty/whitespace-only is X; zero and false remain meaningful typed values. Lists/maps retain structure and ordering. Represent fields with fixed names plus O/X only.

Mixed history fields use a tool-owned semantic projection before comparison. `자격이력자료` retains period and ordered category/acquired/lost rows. `일용근로내역자료` retains period, insurance_types and ordered month/workplace/work_dates/days/wage/remuneration/worker_category row columns. Derived coverage, copy consistency, selection, confidence and geometry remain excluded; only the fixed field name and resulting O/X leave memory.

Agreement uses existing semantic projection (`documentai_bench._semantic_value`) then exact typed equality; exclude evidence geometry/confidence, normalize dates to the existing JSON representation and parse only the existing known structured fields. Do not apply fuzzy matching, tolerances, generic whitespace stripping or staged field normalization without an explicit contract change. Both sides must be present: absent-both is X, not O. These are agreement rates, not accuracy against independent truth.

- Extraction denominator: all successfully classified/processed files of the relevant kind, for every field in that kind's registry, including missing fields. Report failed/unclassified populations separately.
- Engine pair denominator: completed successful selected engine pairs using the own kind's field registry. Different Apple kind gives X for those fields rather than disappearing from the denominator. If an engine is unavailable/failed, comparisons are N/A with a fixed reason and excluded counts.
- Full-text reference: eligible only for PDFs with non-whitespace text on **every** page. Build geometry-aligned words at the same raster scale directly from the original text layer, run the same classifier/extractor/attachment path without OCR and without a slot hint. Never let the production 50-character threshold silently invoke OCR for the reference. Reference kind disagreement gives X; reference processing failure is explicit N/A. Mixed/no-text PDFs and images are N/A.
- Primary row kind and upload verdict belong to own; engine records retain independent kinds, field presence, fixed failures/skips and time.
- Measure each engine's processing (OCR, classification, extraction/postprocessing) once; exclude inventory, summary, serialization, fsync and comparisons. Also retain OCR elapsed time if measured by existing callable. Per-page time divides by actual processed page count; zero-page cases retain elapsed attempts with null per-page time.

## 4. Resume and interrupted writes

Serialize a complete safe row in memory; append using a complete write loop, then `flush`/`fsync` before marking that ID complete in memory. Single-process advisory output lock prevents concurrent writers but introduces no workers. Atomically update metadata through checked siblings and restrictive permissions outside the read-only processing boundary.

On restart, stream and validate prior rows, collecting completed IDs. A valid final JSON object without newline can be completed safely; truncate only the incomplete final record back to its start. Reject malformed newline-terminated records, interior corruption, duplicate IDs and incompatible schemas/configuration. Preserve all valid preceding bytes. The output set is bound to root/engine/vocabulary settings; incompatible settings require a new out directory, not silent mixing. Same ID remains completed even if its file later changes; source refresh/reassessment is outside this resume contract. New group IDs append rather than renumber existing rows.

Run-level inventory counters are a replaceable snapshot, not increments added across retries. Skip the entire output directory by rejecting root/output overlap beforehand. Interrupt after a completed row preserves it; an in-flight file is retried. A completed per-file error row is terminal for this output set.

## 5. Summary and errors

`--summarize --out FAKE-output` validates metadata/rows and imports no OCR backend. Print tables of numeric counts/rates with fixed semantic row/column labels, never paths/groups/source IDs. Include separate NOT_ASSESSED/SKIPPED/ERROR rows and extraction/agreement numerators and denominators for every rate. Print the two work mappings and the unmapped outcome using fixed labels. Separate date-policy codes into a 기준일 정책 사유 table, including DOCUMENT_ISSUED_TOO_EARLY, DOCUMENT_ISSUED_AFTER_APPLICATION and other existing announcement/application-period issuance checks. Keep image quality, missing pages, classification failure and field metrics in their own quality tables; do not present a date-policy rejection as an OCR quality failure. Timing: processed-page count, total time, weighted seconds/page, file-level per-page min/p50/p90/p95/max; zero-page failures separate. Do not call agreement accuracy.

Per-file errors use a fixed stage code plus validated exception class; never access `str(exc)`, repr, traceback, OCR error text or arbitrary exception args for output. Continue after a terminal file error; stop safely for configuration, corrupt resume or output-write failures. Exits: 0 completed/no processing errors (optional unavailable Apple skip is permitted), 1 completed with per-file errors, 2 usage/location/resume/output/runtime setup failure, 130 interruption. Verdict FAIL/NEEDS_REVIEW are observations, not CLI failures. Console shows only processed/skipped/total counts and elapsed time; an early unsafe-output error has a nonzero exit and no diagnostic text.

## Compatibility and rollback

No production migration or rule change. Delete only newly authored tool/test/docs through a reviewed patch to roll back; never delete user outputs or sources. Schema/policy/field-registry changes require a new output set. Apple native execution and HEIC decode are technical capability probes to validate on synthetic inputs after approval; do not claim successful support from source inspection alone.
