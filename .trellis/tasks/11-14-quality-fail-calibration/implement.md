# Execution and validation plan

## Review gate

- [x] Obtain task-creation consent and create the planning task.
- [x] Create `fix/quality-fail-calibration` from clean main.
- [x] Inspect quality source, required-field ordering, screen/API projections, postprocessing and submission-time rechecking.
- [x] Persist PRD, design, test-expectation inventory and research.
- [x] Obtain implementation approval with the user correction requiring unknown-type low-quality FAIL. Report that the expectation-change inventory reduces to four tests.
- [x] After approval, ran task.py start. Use the Trellis before-dev/implement/check routing for the active platform, loading the curated context manifests and task artifacts.

## 1. Capture the unchanged baseline

Run the two pytest suites and each of the 18 scenario modules sequentially, recording exit codes and actual counts. Run frontend validation. Keep each package's logs separate. Tests use synthetic documents and isolated temporary databases/storage. Compare the current results against the supplied baselines before attributing failures to this task.

```sh
.venv/bin/python -B -m pytest engine_v2/tests -q
.venv/bin/python -B -m pytest demo/backend/tests -q
```

Execute every `demo/backend/tests/run_p*_scenarios.py` module in numeric phase order. The module numbers present are 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19 and 20. Record per-module checks and the aggregate, including modules that return failure. Use a Python subprocess runner to preserve output/return codes without concurrent shared-state scenarios.

Run from `demo/frontend` sequentially.

```sh
npm test
npm run lint
npm run build
```

Run synthetic measurement v2 before any production or test-expectation edits. Choose a fresh temporary directory and fresh destinations. This command generates its own fictitious inputs.

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output /tmp/quality-fail-calibration-before.json
```

The shown output basename is an example for this task's generated synthetic report. If it exists, use a fresh temporary directory because the tool refuses overwrites. Preserve the paired JSON, numeric rows checkpoint and Markdown report. Record Python/OCR dependency versions and local font/model identity without installing or updating dependencies as part of the comparison.

## 2. Implement the approved conjunction

1. Load the relevant backend specs, task artifacts and research. Recheck the exact existing essential-unreadable branches.
2. Finalize LOW_IMAGE_QUALITY dynamically using existing essential-field assessment evidence. Preserve measured thresholds, independent hard failures and the review floor.
3. Use the same grade finalization after receipt/consent postprocessing. Preserve exactly one quality finding across retries and public direct-check calls.
4. Add grade-specific messages and action text.
5. Use the same shared quality rule in upload finalization and submission-time engine review, carrying assessed classification/essential-readability context. Preserve raw scores and legacy caller compatibility, plus independent content FAIL precedence. Add the smallest defaulted bridge needed in the adapter/engine models and stage1 aggregation.
6. Add focused regression coverage. Edit only the specifically approved old expectations, retaining their coverage. Report and wait if additional old-test expectations change.

## 3. Compare synthetic measurement v2

Run the same command after implementation with a fresh `quality-fail-calibration-after.json` destination. Keep samples=5 and seed=20261113. Verify matching source_metadata fingerprints, the 410 case keys and source-generation code, fonts and model assets.

There are 25 normal_baseline, 150 stress, 75 quality_defect and 160 content_defect pairs. Each has reference A and actual own-OCR B stages, for 820 stage evaluations. The historical reports are background evidence. The newly run before report is the baseline for this task.

Report before/after/delta with counts and denominators for A and B separately.

- False rejection among expected VALID cases, separately for normal_baseline, stress and their combination. Follow the existing definition requiring final FAIL and a FAIL-severity allowlisted reupload code.
- False acceptance, defined as PASS on a negative case, separately for quality_defect and content_defect.
- The same comparisons by document type and condition, plus full PASS/NEEDS_REVIEW/FAIL/error distributions and changed individual case keys.
- Verify extraction/classification/field metrics as an invariant for this verdict-only task. Investigate any unexpected drift before comparing verdicts.

Keep corpus labels, defect groups and metric definitions fixed. NEEDS_REVIEW has its own distribution and does not count as PASS. In either stage, stop and report if a defect-group or finer-slice false-accept rate increases, or if any new defect PASS appears even with offsetting recoveries. Preserve both reports and the changed-case evidence. Do not resolve an increase by relaxing the acceptance gate or relabeling the corpus.

## 4. Full verification and spec review

Run focused tests, then full engine/backend suites and all 18 scenarios sequentially, then frontend test/lint/build. Inspect the full task diff. Update the backend policy spec with the accepted conjunction, grade-specific guidance and submission bridge. Apply Trellis quality-check and spec-update requirements.

## 5. Pre-commit approval gate

Present the complete list below and wait for explicit approval.

- `git diff --stat main`, current branch and every changed path including task artifacts.
- Engine_v2 actual passed/skipped/failed versus 1,448 passed and 3 skipped.
- Backend actual passed/failed versus 1,252 passed.
- All 18 scenarios with per-module counts, aggregate checks versus 1,885, and failures versus zero.
- Frontend npm test, lint and build results.
- Approved old expectation changes with actual before/after values and reasons, plus new-test count deltas.
- Synthetic v2 before/after rejection and acceptance comparison, changed cases and any unresolved observations.
- Proposed commit message and explicit file grouping following the Trellis commit preamble.

This gate precedes any commit. Real-document remeasurement is performed by the user.

## Completed execution evidence

- Unchanged baseline and final full verification completed with zero failures.
- Final parity file adds 44 cases, including accepted alternatives and duplicate document orders.
- Approved existing expectation changes are confined to four functions, confirmed against main by AST comparison.
- Two independent Trellis checks completed. Final focused review passed 310 tests.
- Fresh final v2 comparison completed with matching input/environment/field evidence and zero new defect PASS or increased acceptance slices.
- Policy spec was updated and reviewed.
- See research/validation.md and research/measurement-comparison.md for actual counts, denominators, limitations and changed case IDs.
- Commit approval is pending after presenting the full main-relative diff and verification tables.
