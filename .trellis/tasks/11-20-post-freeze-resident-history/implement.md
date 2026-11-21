# Implementation and verification plan

## Ordered gates

- [x] Verify clean starting tree, frozen HEAD/tag and absent target branch; create requested branch.
- [x] Obtain planning consent, create one `planning` task, inspect tracked source/tests and write planning artifacts.
- [x] Present final summary; obtain explicit approval before `task.py start`, product/test edits or regression execution.
- [x] After approval, activate this task and apply development/check skills inline. No parallel task/agent and no global Trellis configuration change.
- [x] Before source edits, run unchanged full engine/backend baseline suites. Stop on existing failures.
- [x] Before source edits, generate fresh 410-pair and G1/G2 synthetic baseline reports using the current frozen source; do not read historical results.
- [x] Add new synthetic A-H tests without editing existing expectations, then implement the smallest extractor/adapter changes.
- [x] Run new tests, related existing tests, full suites, repeated scenarios, frontend checks and fresh synthetic reports below.
- [ ] On an existing-test failure or increased false PASS, stop further modifications and report cause/impact; do not adjust expectations.
- [x] Complete full-scope file-by-file diff, spec and privacy review; record actual counts separately from supplied targets.
- [ ] Present concrete file grouping for Trellis commit review after successful checks. Stage each file explicitly, check all five user-specified forbidden literals, commit with the requested message and inspect one-line log. Never amend or push.

Return to planning review if implementation would materially change this design or scope.

## Planned implementation files

1. `engine_v2/extractors/resident_abstract.py`: split-header evidence, safe date fragments where supported, candidate coverage and scoped incompleteness metadata.
2. `demo/backend/ocr/localocr.py`: additional history issues through the existing uncertainty contract.
3. `demo/backend/rules/doc_check.py`: reason detail/comment only if needed; retain verdict logic.
4. New `engine_v2/tests/test_resident_history_continuation.py` and `demo/backend/tests/test_resident_history_continuation.py`: synthetic helpers and A-H tests.
5. Task artifacts and, if implementation establishes durable new knowledge, a small update to the existing backend document-form contract.

Preprocessing, shared layout, OCR/model assets, rulepacks, DB and frontend source remain outside the edit scope.

## Synthetic matrix

| Case | Required variations/assertions |
|---|---|
| A | One-page history exact content/count/provenance; preserve ordinary PASS and existing one-entry review. |
| B | Eight chronological page-one rows plus two page-two rows, exact ordinals 1..10; correct final residence fields and valid verdict. |
| C | Two-line number/address/date/holder headings; combined/separated label tokens, font height/scale/small skew; exactly the same ten rows. |
| D | Missing categories, excessive header gap, one readable and one unread row, ambiguous date-to-row mapping; no guessed entry or prior-page mutation; engine/backend review. |
| E | Unrelated prose/table, dates/ordinals elsewhere, scattered terms, reversed columns and attachments after valid history; no history issue; retain existing page-policy result. |
| F | Header-label split separately from date-value split; unique adjacent fragments versus competing dates, overlap, invalid calendar date, cross-column/row fragments and letter misreads. |
| G | Duplicate/missing pages, damaged/missing/final ordinal, blank/header-only repeats, numbered notes, cross-page continuation. Add new uncertainty to independently confirmed date/identity/page FAIL and preserve its status/code. |
| H | OCR letter/digit lookalikes, geometry threshold boundaries, unsupported column displacement, scale/skew; no invented values or false PASS. |

Check extraction state and final engine/backend verdict. Assert exact synthetic history in tests without printing values. Attachment tests distinguish new history findings from independent pre-existing page checks.

## Environment and execution safety

Repository root unless otherwise stated; use existing `.venv/bin/python` and frontend executables, whose presence was checked during planning. No installs/downloads. Use a fresh dedicated `/tmp` directory for logs and reports; never overwrite existing results.

```sh
export JBAI_ALLOW_REAL_DOCS=false
export ENGINE_V2_OCR=own
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
```

Inspect test/scenario execution hooks to confirm external transports are mocked. Isolated flag tests may exercise an enabled value only with mocked transport; no real-document/API path is enabled. Do not run any live/demo-reset option.

## Verification commands

New tests:

```sh
.venv/bin/python -B -m pytest engine_v2/tests/test_resident_history_continuation.py demo/backend/tests/test_resident_history_continuation.py -q
```

Existing related tests, selected only from tracked source filenames:

```python
from pathlib import Path
import subprocess

existing = [
    path for root in (Path('engine_v2/tests'), Path('demo/backend/tests'))
    for path in sorted(root.glob('test_*.py'))
    if ('resident' in path.stem or 'address_date' in path.stem)
    and path.name != 'test_resident_history_continuation.py'
]
subprocess.run(['.venv/bin/python', '-B', '-m', 'pytest', '-q', *map(str, existing)], check=True)
```

Full suites, also used for the pre-edit baseline:

```sh
.venv/bin/python -B -m pytest engine_v2/tests -q
.venv/bin/python -B -m pytest demo/backend/tests -q
```

All 18 scenario modules sequentially, two passes (P2-P9 and P11-P20):

```python
from pathlib import Path
import subprocess

modules = sorted(Path('demo/backend/tests').glob('run_p*_scenarios.py'))
assert len(modules) == 18
for repetition in range(2):
    for path in modules:
        subprocess.run(['.venv/bin/python', '-B', '-m', '.'.join(path.with_suffix('').parts)], check=True)
```

Frontend, working directory `demo/frontend`, verification only:

```sh
./node_modules/.bin/tsc -b
./node_modules/.bin/oxlint
./node_modules/.bin/vite build
```

410-pair synthetic measurement before/after with identical source settings:

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output /tmp/RESIDENT_TASK_UNIQUE_DIR/paired-before.json
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output /tmp/RESIDENT_TASK_UNIQUE_DIR/paired-after.json
```

Replace `RESIDENT_TASK_UNIQUE_DIR` with a newly created directory. Execute each command at its respective phase, not both after editing. Require 410 cases, 235 negative cases and zero own false acceptance. Compare only these freshly generated synthetic status/code metrics for FAIL-to-PASS changes and valid-case review counts; never read real/holdout individual rows. Keep corpus, truth and reporting implementation unchanged.

Aggregate every status transition separately for reference and own stages, explicitly listing PASS-to-NEEDS_REVIEW, NEEDS_REVIEW-to-PASS, FAIL-to-PASS, PASS-to-FAIL and other changes. Output counts only, without per-document keys or values. Date-value joining remains lower priority and is omitted unless a demonstrated need justifies it.

G1/G2 before/after, separate new logs:

```sh
.venv/bin/python -B -m engine_v2.tools.g1g2_report --sets presentation validation
```

Report presentation/validation separately, without combining fixed denominators. Presentation target: G1 25/25, G2 165/165, supplementary INS4 25/25. Record actual validation-set scores; do not assume presentation targets describe its baseline.

## Final review/reporting

- Report actual pass/fail/skip counts and warnings. Missing assets/dependencies block a complete-verification claim and do not authorize installation.
- Run `git diff --check`, inspect every changed file, classify dirty paths and scan staged content for privacy/secrets. Check zero occurrences of each of the five specified literals without printing matching secrets. Stage files one at a time.
- Recheck frozen tag object/peeled commit and unchanged original branch references. Preserve annotated tag object `6bce0930f8a8482ad8e3ec1e9001aacad6999851` and target `bdd8aade18cd0885ad7549011af5b21241c344b8`.
- After all gates, requested commit: `fix: recover multi-page resident history and flag incomplete tables`; verify `git log --oneline -1`. No amend or push.
- Final implementation report covers all 14 user-requested items, including synthetic 8+2, actual verdict transitions, 410-pair changes, limitations and real case 81 not executed.
- Later present the real-case diagnostic method only after verifying its actual interface; never invent or execute it. Historical holdout 148/150 is not new independent validation.

## Diagnostic follow-up execution

The user supplied the two existing temporary script interfaces and authorized synthetic-only compatibility work. The originals are preserved. Version 2 PDF/number tools pass 12/42 synthetic self-tests; a guarded numbered-path integration reads 8+2 entries from authored bytes without accessing real metadata. The separate own-render sample produces 2/10 and review on both frozen and current extractors, with explicit incomplete/nonzero status; do not change its expected count or treat it as successful recovery. No real numbered invocation was executed.
