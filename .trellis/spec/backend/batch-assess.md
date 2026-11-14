# Value-free batch assessment

## 1. Scope / trigger

Apply to `engine_v2.tools.batch_assess`, its new synthetic tests and batch documentation. This is sequential per-document observation, not an application/household eligibility engine. Do not change OCR/classifier/extractor/assessment/verdict operating code or existing tests to satisfy batch measurements. No multi-document income or work-continuity assessment, identity comparison, remote OCR, model download or source rewriting.

## 2. Signatures

```text
PYTHONPATH=. python -B -m engine_v2.tools.batch_assess --root FAKE-input --out FAKE-output --engines own [applevision]
PYTHONPATH=. python -B -m engine_v2.tools.batch_assess --summarize --out FAKE-output
```

These are fictitious paths; actual output destinations must still pass location checks. Own is required; only optional AppleVision is accepted. Summary neither traverses input root nor runs/imports the OCR backend, and must remain read-only even on failure.

## 3. Contracts

- Process only PDF/JPG/JPEG/PNG/HEIC/GIF/JFIF, case-insensitively. Preserve root-relative IDs exactly. Stable numeric groups derive from the first directory below root, with 0 for root files. Hidden paths and unsupported formats are counted by bounded extension label only, without content reads; do not follow symlinks.
- Apply `verify_cases._private_location` to actual output directory/files/atomic siblings. Inside the checkout requires ignored **and** untracked, not merely untracked; outside is an operator-runtime option. Reject output/input overlap, source aliases/hardlinks and unsafe output targets. Git location checks stay outside the read-only processing guard.
- `run.json` binds schema/policy/root/engines, persistent group map and replaceable exclusion counts. `results.jsonl` is append-only for completed documents. Run-level errors are exit-only; never write a catch-wide error artifact after failed validation or lock acquisition. Per-file results retain fixed error codes and validated exception classes.
- Rows contain only schema/relative ID/group/page counts, fixed failure metadata, detected kind, canonical slot/work category, document status, reason code/severity pairs, identity=`미검사`, reviewed field names, engine presence states/times and field agreement O/X. Never serialize OCR, extractor, assessment or evidence objects. Preserve no original text, extracted values, exception messages/tracebacks, confidence numbers or value hashes.
- Inspect all pages, render PDF OCR inputs in memory at 300 DPI, then run explicit engines. Text-layer PDFs must not bypass own OCR. GIF frames use existing page contracts; unsupported local decoders produce a fixed per-file DECODE_ERROR and processing continues.
- Classify body/geometry without expected upload slot first. Reuse existing extraction/conversion and `read_document` finalization through a memory adapter. Assessment then calls shared `upload_assessment.assess_upload` with original path/extension, cached own result, `identity=None`, no identity callback or DB loaders. Paper consent retains the shared paper-scan path. Do not substitute benchmark-only dates for canonical program criteria.
- Approved policy is double_savings defaults. Only INSURANCE_4 maps to EMPLOYEE (직장가입자) and BIZ_REG_PROOF to BUSINESS (사업소득 사업자) for work_proof. Other undetermined work kinds are NOT_ASSESSED/WORK_CATEGORY_UNMAPPED; kinds with no relevant slot are NOT_ASSESSED/SLOT_UNAVAILABLE. No invented subsidy selection or authenticated applicant context.
- Own delegates local pinned CPU recognition. Apple delegates its production callable with a scoped `_with_tempfile` bridge delivering PIL Image from BytesIO; retain existing language/bbox behavior without temporary PNGs. Optional unavailable Apple is SKIPPED/ENGINE_UNAVAILABLE; actual processing failures remain distinct errors. Restore every patch/log/FD boundary on failure/interrupt.
- Wrap imports, inspection, engines, extraction and assessment in shared quiet/read-only suppression plus local network prohibition. A swallowed write/network attempt remains a processing error. Bytecode is disabled before backend imports; use `-B`.
- Field vocabularies are reviewed per type and exclude confidence/validation/evidence objects. Compare semantic values in memory using existing semantic projection and exact typed equality, preserving list order; absent-both is X. Engine type disagreement cannot disappear from agreement denominators. Missing/unavailable/failed populations remain separately counted.
- Mixed history fields retain reviewed semantics only: `자격이력자료` compares `period` and ordered `rows` with category/acquired/lost; `일용근로내역자료` compares period/insurance_types and ordered month/workplace/work_dates/days/wage/remuneration/worker_category row columns. Coverage basis/years, derived coverage, copy consistency, selection, confidence and geometry do not affect these field comparisons. Unknown arbitrary field names are omitted rather than recorded.
- A text-layer reference is eligible only when every PDF page has non-whitespace text. Construct geometry-aligned words without OCR, independently classify/extract with identical attachment scoping, and record only own/reference agreement. This is a silver reference, not independent accuracy.
- Each completed row is immediately fsynced. Restart skips completed IDs including terminal error rows. Recover only an incomplete final record; preserve valid rows, reject interior corruption/duplicates/config incompatibility. Same relative ID remains completed even after source changes; refresh requires a new output set.
- Console during batch execution contains counts and elapsed time only. Summary uses numeric tables with fixed labels; every percentage includes numerator/denominator and zero denominators are N/A. NOT_ASSESSED, SKIPPED and ERROR have explicit rows. State the two work mappings in the summary.
- Calendar reasons DOCUMENT_ISSUED_TOO_EARLY and DOCUMENT_ISSUED_AFTER_APPLICATION appear under **기준일 정책 사유**, separately from classification/quality/page/field/agreement metrics. Declared-date consistency is not calendar policy. Keep all original per-document reasons; separation changes presentation, never verdict rules.

## 4. Validation and error matrix

| Condition | Result |
| --- | --- |
| Completed run, including observed document FAIL/review | Exit 0 if no processing errors |
| Optional Apple unavailable | SKIPPED with fixed code; continue |
| Corrupt/encrypted/undecodable supported input | Fixed per-file error/class only; durable completed row; continue; exit 1 |
| No classified type/applicable slot/work mapping | NOT_ASSESSED with fixed cause, separate from processing error |
| Invalid arguments/location/resume/config or output failure | Exit 2, no argument/value echo or error-artifact write |
| Keyboard interruption | Exit 130; previously fsynced rows retained |
| Invalid summary input | Exit 2, no writes and no content echo |

## 5. Good / base / bad cases

Good: a newly generated nested corpus records one row per supported file, resumes without changing completed row bytes, and produces numerator/denominator tables. Base: existing upload verdicts and all old tests stay unchanged. Bad: a tracked output, a source-alias results file, an OCR value disguised as a field name, both missing fields counted O, a date-policy FAIL described as OCR quality failure, or an Apple temporary raster written then deleted.

## 6. Required tests

Use fresh synthetic files and fake Git roots contained in the actual checkout when the user restricts outside access. Bind TMPDIR/pytest basetemp there. Existing backend test initialization reads its samples directory: use an isolated tracked-source copy with newly generated samples rather than inspecting pre-existing ignored samples. Link only repository-contained dependency model/font assets, not input trees.

Assert all allowed extensions/hidden exclusions/group IDs, full/partial/short text coverage, corrupt/encrypted/decode failures, both work mappings and unmapped kinds, slot-free classification, original shared assessment with identity None, memory-only engine invocation, all O/X/denominator states, durable restart/tail repair, closed-schema rejection, resolved locations/aliases, and zero DB/network/source/cache writes. Sentinel values in OCR/fields/messages/log/native noise/evidence must be absent from output and every generated result artifact. Summary backend-import/root-traversal spies and error read-only tests are required.

Before commit report new focused tests plus full engine/backend/scenario/frontend results, `git diff --stat main`, actual synthetic CLI summary output and unchanged old-test/operating-code evidence. Wait for explicit commit approval.

## 7. Wrong versus correct

Wrong: choose an extractor from a guessed slot, use the global fallback chain, dump `fields`, retry completed errors implicitly or suppress date-policy findings. Correct: classify independently, call existing algorithms under a bounded in-memory adapter, project reviewed metadata, retain terminal rows and group date-policy reasons separately in summary.

Wrong: repair arbitrary invalid JSONL or append an error while summarizing. Correct: recover only an incomplete tail during an explicit batch resume and keep summary strictly read-only.

## 8. Explicit ID selection

Signature: `python -B -m engine_v2.tools.batch_assess --root FAKE-input --out FAKE-output --ids FAKE-selection.txt [--engines own applevision]`. All example paths are fictitious. `--summarize --ids` is an argument error.

- Read UTF-8 LF/CRLF lines as exact root-relative POSIX IDs; preserve spaces/case and remove line endings only. Ignore empty lines. Apply `_private_location` to the actual list path outside the processing guard. Reject a list within the output tree and aliases/hardlinks to output metadata/records/lock before mkdir, lock acquisition or tail repair. Do not mutate the selection file.
- Deduplicate repeated entries; count/exclude absolute/traversal IDs as outside-root. Count/exclude noncanonical, hidden, unsupported and other invalid entries, and missing inventory members (including ignored symlinks). Process only valid unique listed entries. No valid entry means no document processing.
- Emit only fixed selection labels with numeric `selected`, `not_listed`, `duplicates`, `outside_root`, `missing`, `invalid` counts. Never print list names, entries, source paths or validation exception details. `not_listed` is the eligible inventory outside the valid selected set.
- Metadata-only full inventory still owns extension exclusions and stable group assignment. Filter after inventory without reading unselected document contents. Keep original inventory order, rather than list order.
- Selection is per invocation, not resume identity: keep VERSION/POLICY, closed run/result schemas, lock/fsync/tail-repair, root/engine binding, completed success/error skipping and full-run summary/error behavior unchanged. Previously completed unselected rows remain byte-for-byte. No-flag calls keep their original behavior and console format.
- New synthetic tests must cover count-only output, exact Unicode/spaced IDs, no unselected content reads, duplicates/outside/missing/invalid entries, empty selection, changed/expanded selection with resume, stable groups/schemas, location/alias rejection and old-test preservation.

Good: select two synthetic IDs, count one duplicate and one outside-root entry, process the two valid entries, then skip both on resume. Base: no --ids retains the original four-number progress. Bad: open unselected PDFs, print rejected entries, bind selection to a new metadata schema or rewrite completed records.


## Payment folio observation extension

Per-engine OK/NHIS_PAYMENT records may include optional `payment_paging` with exactly `adopted`, `total_bucket`, `count_mismatch`. Use `payment_paging.statistics` from validated source evidence; never serialize raw markers, exact totals above the reviewed buckets, confidence, amount/date maps or hashes. Vocabulary: adopted O/X; totals 1/2/3_PLUS/UNREADABLE; mismatch O/X/UNREADABLE. X requires both other fields UNREADABLE; O requires a known bucket and O/X mismatch. Conflicting/duplicate markers are X. Missing historical extension stays valid and is counted as EVIDENCE_ABSENT, not rewritten.

`--summarize` reports own/applevision/text_layer separately, denominators OK payment records, adoption counts, total buckets, FILE_LOCAL_MISMATCH counts and unavailable/error/not-requested states. Compare printed total with selected same-form pages, excluding dissimilar attachments. This is a file-local observation, not an application-level received-page count or omission FAIL. Summary remains read-only and imports no OCR/model backend. New tests live in `engine_v2/tests/test_batch_payment_paging.py`; use synthetic temporary inputs/records only.


## Period-denied and folder-multiplicity observations

Optional OK/payment `payment_period_waiver` is O/X/UNREADABLE from `payment_completeness.period_statistics`, never a raw period. O means the necessary confirmed-period condition failed; other blockers can coexist. Summary denominator is each route's successful payment files, with absent historical evidence separated. Keep backward compatibility when the key is absent.

For each route, count nonzero first-level group folders containing at least two successful files of the same canonical kind. Report by kind and overall distinct folders, exclude root group0 from duplicate-folder counts and expose root successful files separately. Per-kind denominator is folders containing that kind; overall denominator is folders with at least one successful classified file. ERROR, SKIPPED, NOT_REQUESTED, NOT_APPLICABLE and unclassified records are excluded and counted. A folder grouping is not verified applicant identity and does not alter any per-file verdict. No folder names, file IDs or paths enter these tables.

Both upload codebases use one-file replacement per explicit slot. Batch uses the same single-file assessment rule: reliable consistent printed total greater than physical file pages can FAIL. Duplicate-folder statistics are separate operational observations, never file aggregation.
