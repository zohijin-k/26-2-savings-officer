# Implementation plan — approved 2026-11-14

## Current gate

- [x] User authorized task creation, research/planning and a new branch on 2026-11-14.
- [x] Created `work/nhis-payment-structure-stage1`; task is now `in_progress` after approval.
- [x] Captured scope/constraints and researched tracked code/synthetic evidence.
- [x] User explicitly approved implementation and five refinements on 2026-11-14.
- [x] Validated both 8-entry contexts and ran `task.py start` after approval.

Current turn is authorized for implementation and synthetic verification; commits still require separate approval.

## Execution order after approval

1. Read final artifacts, applicable backend specs and both context manifests. Record hashes of protected existing test and OCR/extraction/assessment/verdict files. Snapshot dirty paths to avoid including unrelated work. Dispatch Trellis implement with the active task path; do not delegate implementation before approval.
2. Create a fresh exclusively owned ignored in-checkout synthetic sandbox. Build a tracked-source copy with current changes/new test files; generate new samples there instead of using any pre-existing ignored sample tree. Bind TMPDIR and pytest basetemp to this sandbox. Reuse only known local dependency models/fonts, not document trees or external services.
3. Extend existing `engine_v2/tools/layout_dump.py` with explicit `--out` structured mode, closed schema, finite geometry validation and exact-whole-word fixed-label masking. Preserve existing helper behavior and old CLI invocation. No shared-mask behavior change.
4. Reuse guarded in-memory batch inspection and original own/Apple invocation. Capture raw adapter word order and page/box/size/confidence; handle partial text layers without changing batch reference eligibility. Add the approved value-free production extractor/billing diagnostics; no fallback OCR or original-text persistence.
5. Add checked private output, protected source aliases, atomic sibling writing, fixed state/exit projection and path-free console behavior. Exercise restoration after exceptions/interrupts and ensure failed infrastructure writes preserve prior bytes.
6. Add `batch_assess --ids` loading/validation before output mutation, metadata-only inventory filtering, count-only exclusion reporting/deduplication and source-list alias protection. Preserve stable groups, closed run/result schemas, no-flag behavior and durable resume semantics. Reject --ids with summary.
7. Add new `engine_v2/tests/test_layout_dump_structure.py` and `engine_v2/tests/test_batch_assess_ids.py`; keep every existing test file unchanged. Cover the matrices below using independent expected results and synthetic files/providers.
8. Run an actual synthetic PDF through text-layer/own/Apple structured mode, plus a partial-text/multipage case as appropriate. Scan every output and stdout/stderr for fictitious name/date/amount/identifier/Latin/path sentinels and forbidden metadata. Report native availability honestly. Provide an actual masked dump excerpt retaining boxes/order; keep full generated files ignored.
9. Dispatch independent Trellis check for the whole task and resolve findings within approved tooling scope. Apply `trellis-update-spec` to document the new structured mode/selection contracts and update relevant user tool documentation. Do not modify operating-code specs to permit out-of-scope changes.
10. Run final four-branch verification below, syntax/configured lint checks, `git diff --check`, context validation and protected-source hash/diff checks. Present actual results plus `git diff --stat main`, new-file inventory and synthetic dump example. Wait for separate commit approval; do not commit/archive/push/merge while waiting.

## New test matrix

| Area | Required observations |
| --- | --- |
| Masking | Digits, all Hangul/Jamo, uppercase/lowercase Latin, mixed labels and values, exact labels vs prefix/suffix/whitespace variants, punctuation/symbol preservation, only module-constant vocabulary, no region/prose/function-local-label exceptions, split/merged values, existing RRN stars, non-Latin alphabet masking |
| Structure | Three fixed engine records; multi-page indices; identical page geometry; exact unrounded boxes; derived width/height; adapter order and confidence preserved; split, word, cell and line-shaped inputs; no premature grouping; no arbitrary result serialization |
| Diagnostics | Observed partial/full nine-header group counts, allowlisted headings and validation names; month counts; independent period conflict/uncertainty vs range/confirmed/uncertain amount omission; scoped billing checker parity; no values in diagnostic projection |
| Input/capability | Synthetic text/image/partial-text PDF, images/multipage frames where existing decode supports them; text absence; optional unavailable Apple vs actual error; malformed geometry; guard/network/write failures and restored contexts |
| Output safety | Output/temp policy, ignored/untracked vs tracked/unignored, resolved symlinks and source aliases/hardlinks; no new ignore rules; prior output preserved on failure; no source-derived name, original words, raw logs/raster/cache, traceback or path in console/artifacts |
| Selection | Exact root-relative IDs, Unicode/case/spaces, CRLF/final newline/blank lines, duplicate count/deduplication; absolute/traversal/empty-component/backslash/NUL/missing/unsupported/hidden/symlink count/exclusion, list location and output aliases, fixed error/no echo, no output mutation for invalid list |
| Processing/resume | Only selected content opened; deterministic original inventory order/groups; no --ids equals old behavior; completed success/error IDs skipped byte-for-byte; changed/subset selection appends only eligible new rows; persistent groups; unchanged schemas/locks/fsync/tail repair/full-run error and summary semantics |
| Synthetic leakage | Inject fictitious values into words, input/output/list names, dependency logs/native stdout/stderr and exceptions; assert absence from every generated artifact and captured console. Assert expected character projection as well as sentinel absence. |

## Verification commands after implementation

Run Python suites from the fresh synthetic source copy using the existing repository virtual environment and its installed dependencies. `FAKE-sandbox` below is a placeholder, not a real-document location. Bind TMPDIR and pytest `--basetemp` to newly created sandbox directories.

```text
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests/test_layout_dump_structure.py engine_v2/tests/test_batch_assess_ids.py -q --basetemp FAKE-sandbox/focused
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests -q --basetemp FAKE-sandbox/engine
PYTHONPATH=. .venv/bin/python -B -m pytest demo/backend/tests -q --basetemp FAKE-sandbox/backend
```

Run all 18 tracked `demo.backend.tests.run_p*_scenarios` modules sequentially in the isolated copy, without --live/remote options. Capture only module IDs, exits and numeric counts into tracked validation notes. P14 is exit-verified without adding an invented numeric count. Run `npm run lint` and `npm run build` in the primary `demo/frontend` directory (lint can ignore an ignored mirror). No Python lint/type-check command is presently configured; AST/syntax verification must not be represented as type checking.

| Validation group | User-supplied comparison baseline | Required report |
| --- | --- | --- |
| engine_v2 | 1,448 passed / 3 skipped | Actual passes/skips/failures; explain only new-test increments and any real differences |
| demo/backend | 1,296 passed | Actual passes/skips/failures with unchanged assertions |
| scenarios | 18 modules / 1,885 passed / 0 failed | Each exit and aggregate; no counting changes |
| frontend | lint and build | Both exits and any material existing limitation |

Read tests/entry points before execution to prevent private/live input access. Existing suite assertions may not be weakened, edited or skipped to match baseline counts. If a requested check cannot run within this boundary, report it and return to review rather than claim a pass.

## Rollback and approval points

- Before task activation: wait for plan approval.
- If safe structure capture would require changing OCR/extraction/verdict behavior, stop and revise the plan.
- If native providers are unavailable, record fixed safe capability outcomes; no downloads/fallback.
- Preserve input files, any old output and completed batch rows. Do not clean up unowned files or reset unrelated changes.
- Before commit: show full requested evidence and the exact proposed commit file/message grouping, then wait for approval. Task-creation/implementation approval does not authorize a commit.

## Final implementation status

Implementation and independent review complete; no commit performed. New tests: 51 structure + 36 selection = 87. Full engine 1,535 passed / 3 existing synthetic-font skips; backend 1,296 passed; 18 scenario modules / 1,885 passed / 0 failures; frontend lint/build passed. All 206 protected existing-source hashes are unchanged. Actual text-layer/own/Apple native synthetic dump passed a 10-sentinel value scan; see validation.md, validation-results.json and synthetic-structure.excerpt.json. Separate user commit approval remains pending.
