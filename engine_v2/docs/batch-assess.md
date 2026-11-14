# Local value-free batch assessment

Run from the repository root with the local dependencies and pinned own models already installed:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.batch_assess \
  --root FAKE-input --out engine_v2/data/FAKE-output --engines own applevision

PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.batch_assess \
  --summarize --out engine_v2/data/FAKE-output
```

All example paths are fictitious. Omit `applevision` to run only own. AppleVision is optional and unavailable platform/installation capability is recorded as skipped; the tool does not install dependencies, download models or invoke remote OCR.

To process only an explicit subset, add `--ids FAKE-selection.txt`. This private UTF-8 file contains one exact path relative to `--root` per line, using `/` separators. Spaces and case are preserved; blank lines and a final newline are optional, and CRLF is supported. The list itself must satisfy the same resolved private-location policy as output and must be outside the output tree. Never commit a real selection list. These examples and validation inputs are synthetic only.

Selection prints only counts: `selected`, `not_listed`, `duplicates`, `outside_root`, `missing`, and `invalid`. Duplicate entries are deduplicated; absolute/traversal paths and invalid, missing, hidden, unsupported or symlink entries are excluded. Only the valid unique selected files are processed, in the original inventory order. A list with no usable entries processes no files. Unselected entries may be inventoried without reading contents, but are never opened for decoding/OCR/assessment. Group numbers come from the full inventory and keep their original meaning. Do not use `--ids` with `--summarize`.

Resume is still keyed by completed relative IDs, including terminal errors: selected completed IDs are skipped. A subset can later be expanded or changed in the same compatible output set; older rows remain untouched. Selection does not change the run/result schema or the root/engine compatibility checks, and the summary and accumulated error exit status still cover all stored rows. Without `--ids`, existing console and processing behavior are unchanged.

The batch recursively inspects PDF/JPG/JPEG/PNG/HEIC/GIF/JFIF files. Hidden paths and unsupported extensions are counted without reading contents. Symlinks are not followed. Relative paths are preserved as file IDs; the first directory below root assigns a persistent person-group number, while direct root children use group 0. This grouping does not establish identity.

`--out` must resolve outside the repository or be both ignored and untracked inside it, using the same policy as `verify_cases`. Merely untracked is insufficient. Source/output overlap and unsafe output aliases are rejected. The tool creates no ignore rule or privacy bypass. Development/testing for this feature uses synthetic inputs entirely inside the checkout; outside-output behavior is tested with contained fake Git roots.

`results.jsonl` contains one durable row for each completed file, including processing failures. `run.json` stores only run configuration, group mapping and exclusion counts. Run-level setup/resume/output errors signal through exit code only, without creating an error artifact. These artifacts contain permitted paths and fixed metadata, page counts, reviewed field names/O/X, reason codes/severities and timing; no extracted values, OCR text, evidence objects, confidence scores or exception messages are written. Batch console output is four numbers: newly completed, already completed, current inventory total and elapsed seconds.

Rerun the same command to resume. Completed IDs, including terminal error rows, are skipped; an interrupted unfinished file is retried. Only an incomplete final JSONL row can be repaired. Valid earlier rows are preserved. Use a new output directory to change root/engines/schema or reassess a changed/completed file. Output writers are locked to prevent concurrent runs; processing itself is sequential in one process.

Assessment uses the existing **double_savings** default document policy after content-based classification, without a slot hint during classification. Only these work_proof mappings are permitted:

| Detected kind | Work category |
| --- | --- |
| INSURANCE_4 | EMPLOYEE / 직장가입자 |
| BIZ_REG_PROOF | BUSINESS / 사업소득 사업자 |
| Other undetermined work kind | NOT_ASSESSED / WORK_CATEGORY_UNMAPPED |

Kinds with no applicable savings upload slot remain classified but NOT_ASSESSED / SLOT_UNAVAILABLE. The tool records document-level verdicts only: no combined income/work-continuity or application-level eligibility assessment. Identity is always `미검사`; authenticated identity is never inferred from OCR. Existing upload rules may therefore legitimately return identity-related review findings. Original extensions are retained for upload-format policy, even when the batch decoder accepts a wider set of inspection formats.

The summary reads saved artifacts only. It separates **기준일 정책 사유** (DOCUMENT_ISSUED_TOO_EARLY and DOCUMENT_ISSUED_AFTER_APPLICATION) from classification, image quality, missing pages, extraction and agreement metrics. Different-period/program documents may trigger policy reasons without demonstrating an OCR defect. Every percentage shows numerator/denominator; NOT_ASSESSED, SKIPPED and ERROR have separate rows. Field agreement requires two present semantic values and exact typed equality after the existing semantic projection; two missing values are X. A full text-layer PDF supplies a silver comparison reference, not independent ground-truth accuracy. Images and mixed/no-text PDFs have no such reference.

Per-engine timing covers recognition/classification/extraction/postprocessing once, excluding inventory, comparison and output writing. Per-page distributions include actual successfully processed pages; failed/zero-page attempts are reported separately. Decoder failures, including unsupported HEIC capability, produce fixed error rows and do not stop other files.

Exit codes: 0 completed without processing errors (document FAIL/review and optional unavailable Apple are observations), 1 completed with per-file errors, 2 setup/arguments/location/resume/output errors, 130 interrupted. Run-level failures use the nonzero exit as the signal, without writing an error artifact or printing arguments, paths or exception messages. Summary is read-only on success and failure.
