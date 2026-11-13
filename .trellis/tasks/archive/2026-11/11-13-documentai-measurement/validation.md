# Final validation

Baseline checkout: `main` at `77eda157916cd3c0bb3b399746987a349949767a`. Work is isolated on `feat/documentai-measurement`. The starting worktree was clean. No push, PR, merge, branch deletion or main mutation was performed.

## Four regression branches

| Branch | User baseline | Final | Comparison |
|---|---|---|---|
| engine_v2 pytest | 1,264 passed / 3 skipped | **1,314 passed / 3 skipped** | Existing suite unchanged; +50 new measurement tests, no failures/new skips |
| demo/backend pytest | 1,252 passed | **1,252 passed** | Unchanged, zero failures |
| Scenarios | 18 modules / 1,885 passed / 0 failed | **18 modules exit 0 / 1,885 passed / 0 failed** | Unchanged; P14 separately succeeds without a numerical assertion summary |
| Frontend | lint + build pass | **lint + build pass** | Unchanged; existing bundle-size advisory remains |

Commands used repository-root `PYTHONPATH=.` and `.venv/bin/python -B`. External OCR credentials were removed from the test environment and real-document opt-in was false. Scenario modules ran sequentially; P6 used its default isolated storage, never `--live`.

```sh
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests -q
PYTHONPATH=. .venv/bin/python -B -m pytest demo/backend/tests -q
# Each demo.backend.tests.run_p*_scenarios module, sequentially, no --live.
cd demo/frontend
npm run lint
npm run build
```

Final engine run took 22.90 seconds and had seven existing dependency warnings. Backend took 89.23 seconds with nine existing warnings. Independent focused review of the two new test files passed all 50 tests. Existing production OCR/extractor/rule/backend files and existing test files have no diff against main.

The first full engine invocation found one failure in the **new** source-preflight test, after reference classification had been made independent: a valid insurance text PDF needed production raw-text-first classification rather than geometry-only classification. Only the benchmark comparator was corrected; full engine was repeated and passed 1,314/3. No existing assertion was changed, skipped or removed.

## Synthetic evidence

The complete matrix has 35 normal-content cases (five types × seven conditions × one repetition) and 42 authored defective cases. It was run once for completion and again after regressions ended to isolate processing timing. All 77 non-timing case results matched exactly. Final normal processing time was 1.3413 seconds/page. Only the second run is the final reported sample; repetitions of the same source are not added to denominators. Each is an actual own image read. All 38 source field values were authored independently and text-layer-preflight tested.

The full 35-cell and 266 per-field/cell tables, all ten requested reupload codes, defective outcomes and weak rankings are in [measurement-report.md](measurement-report.md). Interpretation and candidate-only improvements are in [findings.md](findings.md). No real document was executed. Private-mode tests used newly authored temporary PDFs and temporary Git repositories only.

Runtime: Darwin arm64, Python 3.14.6, ONNX Runtime 1.31.1, PyMuPDF 2.1, Pillow 13.0.0, NumPy 2.5.4, OpenCV headless 4.14.0.94. Existing own CPU sessions use two intra-op threads and one inter-op thread; pinned model verification and existing masks remain enabled. This is local diagnostic throughput, not a deployment capacity estimate. The first page in each separate benchmark process includes model initialization.

## Retained artifacts

- Committed safe outputs: `measurement-report.md`, `findings.md`, `decisions.md`, this validation, and `research/review.md`.
- Temporary synthetic numeric results: `/tmp/documentai-measurement.json`; first comparison run: `/tmp/documentai-measurement-first.json`.
- Final synthetic progress: `/tmp/documentai-measurement-final-run.log`.
- Engine/backend logs: `/tmp/documentai-engine-final.log`, `/tmp/documentai-backend.log`.
- Scenario numeric summary/progress: `/tmp/documentai-scenarios-summary.json`, `/tmp/documentai-scenarios.log`; per-module logs use `/tmp/documentai-run_p*_scenarios.log`.
- Frontend logs: `/tmp/documentai-frontend-lint.log`, `/tmp/documentai-frontend-build.log`.
- All generated source images/PDFs from actual synthetic measurement were temporary and automatically removed.

## Local history and review

1. `58bc164` — docs: plan DocumentAI measurement and privacy boundaries.
2. `6593c96` — feat(tools): measure own DocumentAI fields and upload verdicts.
Additional local commits retain the result/report, archive this task and append the session journal; see the final handoff and the complete git log.

The complete final list and diff are reproducible using `git log --oneline main..HEAD` and `git diff --stat main`. `main` still points at the baseline above. Final working-tree and unchanged-production checks are repeated after the local commits. No improvement candidate was implemented.
