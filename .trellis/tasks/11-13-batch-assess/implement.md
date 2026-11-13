# Execution plan — implementation approved 2026-11-13

## Planning gate

- [x] Read Trellis workflow, backend specs and existing verification/measurement/assessment boundaries.
- [x] Obtain task-creation consent and create `feat/batch-assess` from main.
- [x] Record PRD, research, proposed design and this plan; curate implement/check context.
- [x] User approved final plan/default policy and six refinements: separate date reasons, only two work mappings, per-document scope, continuing decode errors, explicit denominators/states and synthetic summary before commit.
- [x] Ran `python -B .trellis/scripts/task.py start 11-13-batch-assess` after approval and refinement updates.

## Ordered implementation

1. Dispatch Trellis implement agent with active task path and curated context. Keep existing tests and operating code unchanged. Snapshot existing tracked test/production hashes and clean baseline before code edits.
2. Establish an exclusively created synthetic-only sandbox under a repository-local already ignored location. Set TMPDIR and pytest basetemp within it. Never enumerate or reuse other ignored documents/results/models as input. Inspect scenario/test entry points before executing them to avoid live/private modes; no external-input discovery or remote opt-in.
3. Add CLI parsing, safe closed schemas/field vocabulary, deterministic inventory/group mapping and resolved output policy. Reuse `verify_cases` location checks and verification quiet/read-only guard. Keep summary free of backend imports.
4. Add memory-only PDF/image decode and own/Apple invocation bridges. Probe only generated synthetic HEIC and generated text/image samples for native capabilities; no dependency installs/downloads. Test supported extension failures explicitly when a decoder is unavailable. Preserve existing callable algorithms and attachment scoping.
5. Add slot-free classification/extraction capture, fixed-policy requirement resolution, shared `assess_upload` with `identity=None`, value-free projection and exact semantic agreement. Handle no-type/no-slot/missing fields/skips/failures explicitly.
6. Add append/fsync persistence, compatible-run resume, stable group numbers, incomplete-tail repair, immutable valid rows and advisory single-writer lock. Add separate numeric summary tables and progress-only console output.
7. Add a new `engine_v2/tests/test_batch_assess.py` (split only if clarity requires) with independently authored synthetic expected data. Do not modify existing test modules. Cover the complete matrix below.
8. Dispatch Trellis check agent for full task review, privacy-negative cases and cross-layer compatibility. Fix only new tool/tests/docs and rerun affected checks.
9. Apply `trellis-update-spec`, record any new batch/privacy/denominator contracts, and run final full-scope verification. Report real capability limits and actual counts, including skips; do not invent success.
10. Present final result, `git diff --stat main`, four regression branches and actual synthetic example summary and explicit proposed commit files/message. Wait for separate user commit approval. Do not commit, archive, push or merge while waiting.

## Synthetic acceptance matrix

| Area | Cases |
| --- | --- |
| Inventory | Nested first-level groups, root files, Unicode/case-preserved IDs, all seven extensions, uppercase, empty/unusual extensions, hidden files/dirs, unsupported files, symlinks/cycles, excluded files never opened |
| Inspection | Text on all pages, short nonempty text, mixed/blank/scanned PDFs, encrypted/corrupt/zero-page inputs, GIF composited frames, JFIF, HEIC capability success/failure |
| Pipeline | No slot on first classification, own explicit, no fallback/network/download, original upload path/extension, same shared verdict calls, identity None/`미검사`, no database connection/writes |
| Fields | All reviewed type fields, empty/missing/zero/false/structured values, different engine kinds, absent-both X, optional engine skipped/failed, full-text eligibility, exact semantic comparisons, denominator arithmetic |
| Privacy | Synthetic value sentinels in words/values/exceptions/logs/native writes/code/field names/evidence; no sentinels in captured stdout/stderr or every generated output; no content-bearing temporary/cache/image files; monkeypatch/FD/log restoration on all exits |
| Durability | One immediate fsynced row, interrupted in-flight file, partial final write, final JSON without newline, corrupt interior, duplicates, restart skip, error-row completion, new group stability, incompatible engines/root/version, failed output write, lock contention |
| Locations | Fresh fake Git roots inside actual checkout; ignored/untracked vs tracked/unignored; outside fake root without actual checkout escape; symlink target policy, hardlinks/input aliases, tracked descendants, no extra ignore rule |
| Summary | Backend/OCR import spy, no root traversal, fixed tables only, all required count/rate/timing distributions, zero denominators, tampered/unsafe JSONL rejected without echo |

## Validation commands and four branches

All test inputs, generated artifacts and test temporary directories stay in the newly created sandbox. Examples are fictitious placeholders. Set `TMPDIR` to its resolved in-checkout path and pass an in-checkout `--basetemp` where supported. Existing tests are inspected for explicit external/private/live paths before running; do not weaken assertions or quietly report unrun portions as passed. Any unavoidable incompatible existing check is reported separately for user review.

```text
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests/test_batch_assess.py -q --basetemp FAKE-sandbox/focused
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests -q --basetemp FAKE-sandbox/engine
PYTHONPATH=. .venv/bin/python -B -m pytest demo/backend/tests -q --basetemp FAKE-sandbox/backend
```

Then run every `demo.backend.tests.run_p*_scenarios` module sequentially, without `--live` or remote opt-ins. Record each exit and independent pass/fail count (some modules have no count). Run `npm run lint` and `npm run build` in `demo/frontend`. Do not parallelize inference timing or scenario execution. Keep only value-free numeric validation summaries in tracked task artifacts, never captured sentinel/raw OCR output.

| Branch | Main history evidence (not a fresh run) | Required final evidence |
| --- | --- | --- |
| engine_v2 tests | 1,375 passed / 3 skipped, archived paired measurement validation | Baseline plus new test count; actual skips/failures |
| demo/backend tests | 1,252 passed, same archived validation | Actual passes/skips/failures, unchanged tests |
| Scenario modules | 18 exits zero; 1,885 passed / 0 failed across counting modules | Every module exit and current total |
| Frontend | lint/build passed | Both current exits |

Reconfirm history evidence against current source/test collection rather than treating old counts as new results. Also run `git diff --check`, syntax/configured Python lint/typecheck if present, context validation, and hashes/diff proving old tests and operating code unchanged. Report unavailable configured lint/typecheck honestly; syntax checks are not type checking.

## Rollback/review points

- If an input bridge requires modifying operating algorithms or persisting source content, stop implementation and return to planning.
- If native HEIC/Apple functionality is unavailable, retain fixed per-file capability/skip outcomes and report the observed limitation; do not silently install packages or substitute another engine.
- If default policy scope is changed during review, revise PRD/design/context before task activation.
- Preserve all completed JSONL rows on later file failure; no automatic source refresh or output cleanup.

## Current status

Implementation and independent review complete. New focused tests73; full engine1448/3 skipped; backend1252; all18 scenarios1885/0; frontend lint/build pass. Actual own/Apple synthetic8-file run and byte-preserving8-skip resume completed. See validation.md and synthetic-summary.txt. Awaiting final user commit approval; no commit/archive/push/merge performed.
