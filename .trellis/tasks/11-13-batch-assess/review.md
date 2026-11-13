# Independent Trellis check

## Scope and constraints

Reviewed the new `engine_v2/tools/batch_assess.py` and new `engine_v2/tests/test_batch_assess.py` against the task PRD/design/implementation plan and all eight check-context documents. All review inputs are authored synthetic fixtures or source files inside this checkout. A fresh ignored in-checkout review sandbox contains TMPDIR and pytest basetemp. No existing document/sample tree or outside-repository file was searched/opened. No original tests, production OCR/classifier/extractor/assessment/verdict/frontend code, commit, push or merge were changed/performed.

## Findings fixed

1. **Invalid final-record corruption could be discarded as an interrupted write.** `load_rows` caught every invalid nonterminated JSON record and truncated it, including complete duplicate-key and NaN records. Added `_incomplete_tail` to recognize actual serialized-object prefixes (including partial UTF-8, literals and exponents). Complete invalid syntax/metadata and invalid UTF-8 now reject without changing prior or trailing bytes. Only genuine incomplete tails are repairable.
2. **An unknown operating verdict could remain an exit-0 observation.** `_assess` previously projected an unknown status to ERROR but retained NONE error metadata. Unknown verdicts now raise fixed ASSESSMENT_ERROR; the document row records that fixed assessment/error code and validated class, and batch exits 1 while continuing. Injected arbitrary status text never reaches output.
3. **History extraction measurements omitted semantic body fields.** Added reviewed `자격이력자료` and `일용근로내역자료` field names, with explicit in-memory semantic projection. Acquisition retains `period` and rows containing only `category`, `acquired`, `lost`. Daily retains `period`, `insurance_types` and rows containing only `month`, `workplace`, `work_dates`, `days`, `wage`, `remuneration`, `worker_category`. Confidence/geometry, coverage basis/derived coverage, copies consistency and selection evidence do not affect agreement and are never serialized. Row semantic changes produce X; evidence-only jitter remains O.
4. **A later PDF inspection failure discarded known page facts.** The physical page count and confirmed text-layer coverage are now preserved when text extraction/rendering fails after the PDF opened. The fixed OPEN_ERROR retains only the original validated exception class, never its message; subsequent files continue.
5. **A zero-incidence calendar-policy table had no numerical rows.** The two fixed calendar reasons now show explicit numerator/denominator rows even at zero. They remain separate from quality reasons and other document-level reasons.

## Verification

- Focused new synthetic suite: **73 passed, 0 failed**, 5 existing PyMuPDF import deprecation warnings, 21.63 seconds.
- New regression assertions cover complete invalid trailing records remaining byte-identical, genuine incomplete prefixes, unknown verdict privacy/exit semantics, semantic history rows versus evidence-only jitter, known page preservation and subsequent-file continuation.
- Existing focused coverage also verifies the two work mappings and unmapped outcomes, fixed decode errors, independent classification/shared upload calls with identity None, memory-only Apple bbox conversion, field extraction/agreement, immediate durable append/resume, safe locations/aliases, swallowed write/DB/network/process attempts, Python/native/log/exception sentinel suppression, patch restoration on interrupt and strictly read-only backend-free summary in a fresh process.
- Both new Python files parse successfully with `ast.parse`; `git diff --check` passes. No configured Python lint/typecheck command was found; syntax checks are not reported as type checking.
- `git diff --name-only` for existing pipeline/extractor/backend OCR/assessment/backend test paths is empty. Root separately owns original-file hash comparison, the full four-branch regression and actual native-engine synthetic demonstration.

## Remaining limitations / final handoff

- Optional Apple native capability and HEIC decoding depend on the local environment. Tests cover fixed unavailable/error outcomes; the parent separately observed real own/Apple execution on generated inputs. No native capability success is inferred solely from mocks.
- Unknown arbitrary field names are safely omitted rather than recorded. The reviewed semantic registry intentionally excludes validation/evidence-only keys; there is no unknown-field counter in the row schema.
- Run-level setup/location/resume/output failures are exit-only 2 and interruption is 130, with no catch-wide error-file append. Per-file code/class metadata remains in JSONL. Root is reconciling this finalized behavior with planning/user documentation.
- Code and tests are frozen after this review. Root may synchronize them into the isolated regression copy, rerun the fresh synthetic corpus because the semantic field registry changed, update final aggregate evidence and request the separately required commit approval.
