# V2 validation and approval record

## Authorization and scope

The user approved implementation and n=5 after the audit, with seven explicit constraints. Work remains on `feat/documentai-measurement`. Initial HEAD for this approval was `965a634`; main remains `77eda157916cd3c0bb3b399746987a349949767a`. New commits are held for the requested final review. No push/PR/merge/branch deletion/main operation was performed.

Only new staged benchmark tools/tests, usage documentation and this task's records are changed. Legacy measurement/API/tests and all prior result reports remain intact. The source policy is documented in source-decisions.md: no ambiguous original layout or real-possible marking was removed or repaired. No real/private input was read.

## Focused validation and independent review

- Staged core tests cover raw/normalized comparison, missing versus uncalled/error, reference/own same-reader injection, restored instrumentation, independent actual type versus requested slot, read-only protection and safe errors.
- Report tests cover called denominators, groupwise verdict rates, paired losses/recoveries, completeness of identifier vocabularies, raw/normalized micro CER and separate zero-page timing.
- Corpus tests cover five distinct original/source definitions, unchanged original geometry/labels, reference transforms, authored date consistency/font coverage, preserved layout stress, explicit cohort assignment, output overwrite/alias protection, distinct malformed bytes and actual submitted-input uniqueness.
- Independent review findings R01–R04 were resolved. The zero-page timing issue is report-only and uses saved pair rows; it does not require another OCR measurement.

Full final counts, completed artifact arithmetic and four regression branches will be appended after execution. These are pending here until actual completion, not claimed results.

## Planned full verification

```sh
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests -q
PYTHONPATH=. .venv/bin/python -B -m pytest demo/backend/tests -q
# Run every demo.backend.tests.run_p*_scenarios module sequentially, no --live.
cd demo/frontend
npm run lint
npm run build
```

Regression baselines: main engine1,264/3 skipped; previous measurement engine1,314/3 skipped; backend1,252; all18 scenarios/1,885 passed/0 failed; frontend lint/build pass. Expected differences are only new staged measurement tests. Existing assertion files may not be changed or weakened.

## New artifacts (separate from v1)

- `/tmp/documentai-paired-v2-n5.json`: original as-run numeric/code-only stage results, preserved unchanged.
- `/tmp/documentai-paired-v2-n5-reviewed.json` and sibling Markdown: intermediate reviewed snapshot, preserved.
- `/tmp/documentai-paired-v2-n5-final.json` and sibling Markdown: final reviewed report, including opportunity-change attribution; the same stage rows with the final reviewed report aggregation (zero-page timing refinement); new destination, not an overwrite.
- `/tmp/documentai-paired-v2-n5.rows.jsonl`: completed-pair numeric checkpoint.
- `/tmp/documentai-paired-v2-n5.md`: new machine-generated report.
- `/tmp/documentai-paired-v2-n5.log`: fixed-vocabulary progress and final numeric summary.
- Final report will be retained as `measurement-v2-n5-final.md` in this task directory; prior report files are not overwritten.
- Final regression logs use the `/tmp/documentai-v2-*` prefix; old verification evidence is preserved.

The main attribution/weakness tables use expected-valid normal/stress pairs. Deliberately invalid or defective input outcomes remain in group/condition verdict tables, not misinterpreted as intrinsic OCR/classification failures. Apparent percentage changes against v1 are measurement-definition/denominator changes, not operational engine improvements.

## Completed measurement and arithmetic verification

- All410 logical pairs /820 retained stage evaluations completed, zero execution errors. There are82 applicable type/condition cells, each with exactly five sample indices and five distinct submitted-input hashes.
- Cohorts are25 normal baseline,150 stress,75 quality defects and160 content negatives. All25 source fingerprints are unique within type; every rendered source has zero missing font glyphs.
- Initial full run wall time611.1768seconds. Selective replay of10 qualification negative-date pairs took13.6021seconds after correcting source/GT request-year disagreement; input hashes, verdict/type/invocation and every non-request field metric matched. The replay model was warmed to match their originally warm position. Logical sample counts remain410, never420.
- Final aggregation was recomputed from saved/replayed rows, with per-case attribution equality, called/unextracted/error conservation, actual input uniqueness, groupwise verdict numerators and physical-page timing independently checked. Zero-page durations do not enter page numerators.
- Opportunity changes reconcile the full readable field delta:452 own errors −259 A errors =58 OCR-added losses +180 newly called errors −15 recoveries −30 hidden A errors =193. Classification reconciles73 A failures +5 OCR losses −23 recoveries =55 own failures.
- Normal baseline own raw/normalized exact is145/165=87.88%;25 additional fields are classification-gated and excluded, not wrong. Authored-field correct coverage145/190=76.32% equals the v1 original-only29/38; no operating improvement is claimed. Formatting-only exact recoveries are zero in A and B.

## Four final regression branches

| Branch | Main/user baseline | Previous v1 result | Final v2 result |
|---|---|---|---|
| engine_v2 pytest | 1,264 passed /3 skipped | 1,314 passed /3 skipped | **1,375 passed /3 skipped**, 0 failed |
| demo/backend pytest | 1,252 passed | 1,252 passed | **1,252 passed**, 0 failed |
| Scenarios | 18 modules /1,885 passed /0 failed | Same | **18 exits0 /1,885 passed /0 failed** |
| Frontend | lint/build pass | Same | **lint/build pass** |

New staged files have61 passing tests: core30, report21, corpus10. Together with v1's50, engine adds111 tests to main without changing existing tests/skips. Full final engine took23.88seconds with7 existing dependency warnings; backend took70.93seconds with9 existing warnings. Scenario modules ran sequentially, including P14's nonnumeric success check, with58.65seconds total orchestration. Frontend retains its existing bundle-size advisory.

An earlier full engine run already passed1,373/3. After adding opportunity-change decomposition tests and source/GT integration checks, full engine was repeated and passed1,375/3. Backend/scenarios/frontend were unaffected by those report/test-only refinements and their full successful results are retained rather than repeated unnecessarily.

Final evidence: `/tmp/documentai-v2-engine-final.log`, `/tmp/documentai-v2-backend.log`, `/tmp/documentai-v2-scenarios.log`, `/tmp/documentai-v2-scenarios-summary.json`, `/tmp/documentai-v2-frontend-lint.log`, `/tmp/documentai-v2-frontend-build.log`, `/tmp/documentai-v2-final-focused.log`, `/tmp/documentai-v2-checks-final-summary.json`. Raw as-run/intermediate reports remain unchanged; the task-local interim v2 report was retained at `/tmp/documentai-paired-v2-task-interim.md` and the final report has its own `measurement-v2-n5-final.md` name.

## Final review state

Final conclusions are in `findings-v2.md`; complete stage/condition/field tables and timings are in `measurement-v2-n5-final.md`; S01–S08 source evidence is in `source-decisions.md`. No operating OCR/classifier/extractor/adapter/verdict, old benchmark implementation/test or prior report has changed. No real/private source was opened. No new commit has been made since HEAD965a634. User final approval is pending; task is deliberately not archived and no remote/main operation is authorized.

Runtime context: 2026-11-13, Darwin arm64, Python3.14.6, ONNX Runtime1.31.1, PyMuPDF2.1, Pillow13.0.0, NumPy2.5.4, OpenCV headless4.14.0.94. Existing own CPU session settings remain two intra-op/one inter-op thread. Normal/stress timing includes the initial own cold start and otherwise warm sequential operation; it is local diagnostic throughput, not a production capacity estimate.

## Approval received

The user approved applying the reviewed changes with `commit apply`. Local commits group the staged benchmark/tools/tests/usage first and measurement evidence/task records second. Trellis archive and session records follow those work commits.
