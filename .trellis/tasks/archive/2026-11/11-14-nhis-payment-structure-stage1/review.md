# Independent Trellis check

- Date: 2026-11-14
- Active task: NHIS_PAYMENT structure stage 1, implementation approved; separate commit approval remains pending.
- Inputs: tracked code/specs/task artifacts and newly authored synthetic temporary inputs only. No real documents, private input trees or source-document paths/names were inspected or requested.

## Scope checked

Read the nine check-context entries, PRD/design/implementation plan, the complete modified tool paths (`layout_dump.py`, `structure_dump.py`, `batch_assess.py`), both new test files and the new/modified tool documentation/specs. No implementation/check subagents were spawned. Review changes are confined to one newly added test; no operating algorithm or existing test was edited.

## Finding fixed

The new `test_tracked_and_unignored_outputs_rejected_before_processing` originally treated the imported `layout_dump.py` file as necessarily tracked. That assumption fails in the required fresh ignored tracked-source validation copy, which is not itself a Git checkout. The parent observed one new-test failure in that environment. Replaced the environmental assumption with a contained fake Git root and injected `verify_cases.REPOSITORY_ROOT`: a force-tracked file under an ignored directory and a separate unignored target now exercise the actual policy independently of source-copy location. The test verifies rejection before processing and byte preservation. This changes only a new test's setup; no assertion or existing test was weakened.

## Reviewed contracts

- Literal exceptions are the exact 28-string union of existing payment module constants. Original whole words are compared before any normalization; function-local metadata labels and substring/fixture/region additions are excluded. All other word content is character-masked while boxes, order, page numbering and confidence remain explicit numeric evidence.
- The projection is closed: no field dictionaries, raw page text, source names/paths, finding text, exception details or value hashes are serialized. Recognized heading and failed-validation strings use fixed allowlists. Tests scan saved artifacts and captured Python/native/log output for synthetic name, amount, number, date and Latin sentinels.
- Original extractor helpers run through scoped observers; actual observed header clusters and expected-nine quota matches are separate. Government versus legacy/recognition scopes are explicit. Month-anchor loss and billing-check causes remain separate. The latter calls original conversion/billing code and projects its structured period/range/amount/map branches rather than parse finding messages or create a new verdict.
- In-memory forced OCR and partial text-layer preservation reuse existing safe batch components. Missing text/optional Apple capability differ from processing errors. Guarded processing suppresses output and rejects writes/network attempts even when a dependency swallows the immediate error. Only the final safe report is written after leaving the guard.
- Output and atomic siblings follow the existing resolved external-or-ignored/untracked policy. Source/output/hardlink/symlink hazards and prior-output preservation on tested failures are covered. Legacy layout masking/grouping behavior is unchanged.
- `--ids` deduplicates and counts exclusions without path echoes, processes only valid selected content in inventory order and preserves stable group assignment. Root/engine binding, schemas, lock/fsync/tail repair, completed success/error skipping, changed selections and full-run summary/error behavior are preserved; no-flag processing stays compatible.

## Verification

- New focused suites: **87 passed** (51 structure + 36 selection), 5 existing PyMuPDF/SWIG warnings, 13.21 seconds. TMPDIR and pytest basetemp were inside the newly created synthetic sandbox; no original backend sample initializer was run.
- All **206 protected existing test/operating-source hashes are unchanged**.
- AST parsing passed for all five affected Python files; `git diff --check` passed. The repository has no configured Python lint/type-check command; AST parsing is not claimed as type checking.
- Parent owns the final full engine/backend/18-scenario/frontend checks and actual native synthetic dump evidence. This review does not substitute focused results for that gate.

## Outcome and limits

No unresolved implementation finding remains in the reviewed scope. The diagnostic is explicitly a scoped NHIS payment probe under canonical default savings requirements, not a complete upload verdict or proof of real-document accuracy. Partial/missing engine pages intentionally leave document-level diagnostics NOT_RUN rather than turn absent evidence into zeros. Existing upstream resident-number stars remain stars. Final numerical results, synthetic dump example and `git diff --stat main` still precede separate user commit approval; no commit, push, merge or archive was performed.
