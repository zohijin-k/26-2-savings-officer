# Implementation plan — approved

## Gate

- [x] User approved Trellis creation/planning and the branch from main.
- [x] Create branch, PRD, design, execution plan and research/context artifacts.
- [x] Plan approved with mandatory payment-table analysis and symmetric masking/normalization.
- [x] Context validated and task started after approval.

## Ordered work

1. Implement pure numeric OCR metrics and closed result schemas in the new tool (or focused tool-only helper modules if needed). Write independently known synthetic examples for CER, token multisets, reading order, geometry transforms, empty denominators, line coverage, bins and field-cause attribution.
2. Add PDF-only selection and page eligibility. Reuse the production trusted text threshold and body classification. Add deterministic memory-only clean/scan/phone generation and pre-masking observation. Prove zero image/text temporary writes, same variants across engines, observer restoration and normal masked extraction input.
3. Connect independent text-reference and OCR classification/extraction through existing adapters. Keep per-page field reference fixed across variants; count unavailable reference fields, OCR misclassification and errors explicitly. Do not import/call service assessment or verdict tools.
4. Add whole OCR, observable own phase timing and extraction timing; capture numeric thread/cold-start metadata. Reuse resident bands and mandatory NHIS payment reference header/month-row bounds; mark unconfirmed and other-form regions unmeasured. Prove masking and normalization parity with synthetic split identifiers.
5. Add durable document completion JSONL, validated run identity, IDs, per-invocation document limit, locking/fsync/tail recovery and summary JSON/text. Reuse batch internals conservatively; if factoring is unavoidable, first preserve its original public behavior with unchanged tests.
6. Add synthetic integration/privacy/security tests. Cover all exclusions, mixed PDFs, unavailable engines, extraction failures, sentinel leakage through output/unknown keys/exceptions/Python and native logs, attempted writes/network, IDs/limit/resume, output aliases, duplicate/corrupt JSONL and read-only backend-free summary.
7. Create tool documentation for CLI, metric units/denominators, quality thresholds, seed/settings, timing boundaries, mask observation, page-local and silver-reference limitations, partial table coverage and explicit absence of verdict measurement.
8. Run focused new tests. Then run one actual-engine authored synthetic document and both requested installed engines; save only reviewed numeric summaries. Missing dependencies/models get a fixed unavailable report, never automatic downloads.
9. Run full required regressions in a tracked-source-only isolated copy with newly generated synthetic samples. Use the same dependency environment and local model assets. Preserve existing tests and report any failures/reasons before changes.
10. Perform full change review against PRD/design/specs, review lessons for a narrow spec update, inspect all changed paths and verify operating engine/extractor/verdict code and old tests remain unchanged.
11. Stage only reviewed task files, scan staged content for the requested sensitive patterns and real-input path strings without echoing matched content, and present results plus updated commit proposal for approval. No commit/amend/push before approval. No coauthor trailer.

## Required commands (from repository or isolated equivalent)

```text
.venv/bin/python -B -m pytest engine_v2/tests/test_ocr_baseline*.py
.venv/bin/python -m pytest engine_v2/tests
.venv/bin/python -m pytest demo/backend/tests
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; .venv/bin/python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
cd demo/frontend && npx tsc -b && npx oxlint && npx vite build
```

Supplied reference counts: engine 1,641 passed / 3 skipped / 3 xfailed; backend 1,410 passed / 2 xfailed; scenarios 18 modules / 1,885 checks / zero failures. Report new focused tests separately so their addition cannot hide baseline losses. Scenario modules run sequentially and each exit status is recorded. No frontend implementation changes are planned.

## Review artifacts and delivery

- Numeric synthetic smoke summary and measured page-based runtime estimate, with cold-start and single-document limitations.
- Focused and complete regression counts, isolation method and any unresolved failures.
- Full diff statistics against main and unchanged operating-code/old-test evidence.
- Staged sensitive-pattern scan counts; filenames/allowlisted metadata only, no matching source values.
- Two fully populated operator commands in chat only (pilot limit 30, then full resume); never execute them.
- Commit approval request using the scope-corrected message without verdict agreement.

## Rollback points

Before approval: only planning artifacts and branch metadata exist. During implementation: remove new benchmark artifacts and revert only session-owned helper refactors if needed. Existing services require no rollback or data migration. Do not rewrite existing benchmark outputs.

## Final state

Implementation, full review, synthetic smoke and all four regression groups completed. See `validation.md` and numeric synthetic summaries. Commit remains pending explicit user approval. No existing operating code or old tests were modified.
