# Stage-1 validation and commit review

## Scope and isolation

Implementation was approved on 2026-11-14 with all five user refinements. Only layout/batch tools, new tests and documentation/task/spec files changed. No real documents or their locations/names were used or requested. No operating OCR/extraction/classification/assessment/verdict code or existing test was edited.

The verification harness used a fresh ignored in-checkout tracked-source copy with newly generated synthetic samples, isolated TMPDIR/pytest basetemp and only known local model/font dependency assets. It did not reuse existing sample/document trees. All five final tool/new-test files match the versions exercised in that copy. All **206** protected existing-source hashes match their initial bytes. Full scenario modules ran sequentially without live options; JBAI scenarios use their existing authored fake transports.

## Final four-group results

| Group | Baseline | Final | Evidence |
| --- | --- | --- | --- |
| engine_v2 pytest | 1,448 passed / 3 skipped | **1,535 passed / 3 skipped / 0 failed** | 31.51 seconds; +87 new tests; existing synthetic font unavailable |
| demo/backend pytest | 1,296 passed | **1,296 passed / 0 failed** | 86.54 seconds; unchanged assertions |
| scenarios | 18 modules / 1,885 passed / 0 failed | **18 exits zero / 1,885 passed / 0 failed** | Per-module numeric rows in validation-results.json; P14 has no numeric assertion counter |
| frontend | lint/build | **Both exit 0** | Existing large-chunk build advisory; no frontend source changes |

New focused tests: 51 structure + 36 ID selection = **87 passed**, independently reviewed. Original batch tests plus the new ID tests also passed together (109 cases). AST parsing of all five changed/new Python files and git diff --check pass. No Python lint/type-check command is configured; AST checks are not presented as type checking.

The first full engine run exposed one new test's assumption that the synthetic source mirror itself was a tracked checkout. The review replaced only that new test setup with a contained fake Git root and real ignored/force-tracked/unignored states. The final full engine suite then passed. No operating change or old assertion was used to resolve this test-environment issue.

## Actual synthetic three-engine dump

Created an authored payment PDF using the existing fictitious payment cells and CJK TextWriter technique, then ran the actual structured CLI. The final native run exited 0 with empty stderr. Text-layer/own/Apple all returned word arrays and diagnostics. Ten declared synthetic value strings covering name, workplace, date, document/payer numbers, amounts and purpose were absent from saved JSON plus stdout/stderr. The new test suite separately scans every dump artifact/temp sibling and captured output, including injected dependency/native noise and path/value sentinels, and verifies character-shape expectations.

| Engine | Words | Observed component clusters | Matched of nine | Months | Failed validation count | Scoped billing cause |
| --- | --- | --- | --- | --- | --- | --- |
| text_layer | 127 | 9 | 9 | 12 | 0 | NONE |
| own | 107 | 9 | 7 | 12 | 1 | PERIOD_UNCERTAIN_OR_MISSING |
| applevision | 103 | 9 | 9 | 12 | 14 | NONE |

Own selected the legacy reader and failed `monthly_total_matches`; the independent period evidence required review even though twelve month rows were recognized. Apple selected the government reader but retained numeric/arithmetic/information/issue-date failures; a NONE billing cause does not mean the whole document passes. These are observations on one authored synthetic document, not estimates of real-document accuracy or proof of the 275-case measurement cause.

Apple's initial restricted execution returned zero observations without an engine exception. An approved native execution of the identical synthetic command returned 103 observations, without code/dependency changes. The initial observation remains in the ignored synthetic sandbox; the final example uses the successful native execution. This is an execution-environment limitation, not a reason to substitute OCR engines or reinterpret empty results as successful extraction.

`synthetic-structure.excerpt.json` retains the real schema, all engine diagnostics and the first two unchanged word records on each page from this native run; only later word records are omitted for readability. It includes boxes/sizes/order/confidence and character masks. It is explicitly an excerpt, not the full word count. Full generated inputs/dumps/logs remain ignored. Numeric aggregate results and this masked excerpt contain no real-document path or value.

## Diagnostic and selection review

- Literal text exceptions are exactly the 28 strings from existing extractor module constants, completely listed in design.md and checked by a hardcoded-set test. No metadata function literal, fixture fragment, normalized/partial substring or region exception is permitted.
- Diagnostics preserve observed cluster count and quota-limited expected-heading matches separately, original government/legacy scopes, recognized month count, safe validation names and structured production billing branches. Monthly-map missing/unreadable/incomplete evidence is distinguished from period uncertainty, and table-row absence is independent.
- --ids reports selected/not-listed/duplicate/outside-root/missing/invalid counts only, deduplicates/excludes unusable entries, preserves exact root-relative IDs and inventory ordering/grouping, never opens unselected content and skips completed success/error IDs. Changed selection retains compatible run schemas and existing rows. Alias/location and no-flag regressions pass.
- Independent review found no unresolved implementation issue; see review.md. Actual full/native checks use the reviewed final code.

## Approval gate

Present `git diff --stat main`, the four-group results, the actual masked synthetic example with diagnostics and the proposed commit grouping to the user. **Commit approval is pending.** No commit, push, merge, archive or journal commit has been performed.

Proposed single work commit: `feat(tools): add masked payment diagnostics and selective batches`. Include the three tool files, two new test files, tool docs, relevant backend specs/index and this task's artifacts. There are no unrecognized dirty files from before this task.
