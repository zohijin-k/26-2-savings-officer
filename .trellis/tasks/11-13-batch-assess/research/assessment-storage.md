# Research: assessment, locations and regression ownership

- **Query**: Find reusable assessment/location boundaries and resolve the requested four verification branches.
- **Scope**: Repository code, specs and historical task evidence only; no source documents or outside files searched/opened.
- **Date**: 2026-11-13

## Confirmed findings

| Source | Finding |
| --- | --- |
| `demo/backend/tools/verify_cases.py:42` | `_private_location` resolves targets; outside checkout is allowed; inside checkout requires successful default `git check-ignore` and no tracked match. Untracked alone is insufficient. Git output is suppressed. |
| `demo/backend/tools/verify_upload.py:34` | Shared audit hook blocks writes, subprocess execution and SQLite connections, including swallowed write failures. |
| `demo/backend/tools/verify_upload.py:78` | `quiet_assessment` combines logging disable, Python/native output suppression and read-only processing. It does not itself prohibit network events. |
| `demo/backend/tools/verify_upload.py:152` | `_context` builds requirements from program/default criteria without a DB query. Existing CLI defaults to double_savings. |
| `demo/backend/upload_assessment.py:40` | `assess_upload` supports an injected reader, optional identity/loaders and the existing verdict path. Reader receives expected kind, so independent classification must precede requirement selection and cached OCR must be returned unchanged. |
| `demo/backend/upload_assessment.py:73` | Existing check uses original suffix. Batch-supported image extensions must not be silently relabeled as allowed application formats. |
| `demo/backend/rules/required_docs.py:247` | Checklist dispatch distinguishes savings and job programs; job receipt slots depend on subsidy selections rather than document kind alone. |
| `demo/backend/rules/required_docs.py:353` | Savings checklist includes common NHIS/resident types and category-specific work requirements; paper/admin/labor requirements depend on explicit context. |
| `demo/backend/api/common.py:99` | `checklist_from_inputs` owns no-DB requirement construction plus criteria bounds/month/history rules. Reuse instead of benchmark-only dates. |
| `demo/backend/rules/required_docs.py:469` | Existing `slot_for_doc_type` looks for actual upload requirements; classification-only negative kinds do not automatically have upload slots. |
| `.trellis/tasks/archive/2026-11/11-13-documentai-measurement-audit/validation-v2.md:55` | Latest merged historical four-branch result: engine 1,375/3 skipped; backend 1,252; all 18 scenario exits zero, counting scenarios 1,885/0; frontend lint/build pass. This is historical evidence, not a fresh test run. |

## Planning consequences

- Reuse assessment directly with no DB calls and `identity=None`; identity check remains explicitly untested. Do not use `verify_upload`'s rendered output or unrelated application-level eligibility analysis.
- The supplied CLI has no program/applicant context. The proposed policy needs explicit plan approval: savings default requirements, category-specific canonical work requirements, and unassessed outcomes for kinds without an applicable savings upload slot. Do not infer job selection/receipt amount/application context from names.
- Paths are permitted output identifiers in this task, unlike earlier verify_cases snapshots. All other safe-metadata projection and suppression rules remain relevant.
- Interrupted JSONL appends require per-row fsync and validated trailing-record recovery; existing atomic-whole-snapshot writing is a policy reference, not a resumable implementation.
- Use fake nested Git roots and fresh synthetic data inside the actual checkout to test outside-the-fixture location policy without violating the actual repository-only access boundary. Bind TMPDIR/pytest basetemp there during future test execution.
- Full four-branch checks happen after implementation approval and only with synthetic/local inputs; old test assertions remain unchanged. Verify entry points first, since a historical command alone is not proof of compliance with this session's access limits.

## Applicable specs

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/verify-cases.md`
- `.trellis/spec/backend/documentai-measurement.md`
- `.trellis/spec/backend/document-form-contracts.md`
- `.trellis/spec/backend/quality-guidelines.md`

## Research limits

No tests, OCR, source-document reads or native capability probes were run. No implementation approval exists yet. Decode and native Apple support must be observed later using synthetic input, not assumed from imports or platform alone.
