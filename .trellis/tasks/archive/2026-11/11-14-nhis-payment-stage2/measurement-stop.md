# STOP: synthetic false-pass regression

The user-required safety gate failed. Further implementation, measurement and commit work are stopped. Changes remain uncommitted for review; no expected verdict or old test expectation was changed.

## Confirmed result

Before: samples 5 / seed 20261113, 410 pairs / 820 stage evaluations, zero execution errors. After: the monitor stopped the process after 29 completed pairs when one authored negative case newly passed. All 29 completed pairs have identical before/after input fingerprints. The interrupted after run is not a completed v2 comparison and has no full-run after accuracy/rate result.

| Case | Source | Authored condition | Before | After |
| --- | --- | --- | --- | --- |
| `s1_nhis_payment_pages_incomplete` | own | content_defect / pages_incomplete | NEEDS_REVIEW | **PASS** |

Classification remains NHIS_PAYMENT. Metrics for four fields change: 월별고지금액, 월별장기요양보험료, 건강보험료 and 장기요양보험료. Their recovery accompanies the new PASS. The precise recovery branch and interaction with the defect's geometry have not been isolated by additional experiments; that would be further work after the required stop. Do not relabel this case as valid, weaken its expectation, or claim the regression is harmless.

For the **same completed prefix only**:

| Population | Stage | Before false PASS | After false PASS |
| --- | --- | --- | --- |
| All authored negatives in 29 matched pairs | own | 0/15 | **1/15** |
| Payment authored negatives in that prefix | own | 0/5 | **1/5** |
| All authored negatives in that prefix | reference | 1/15 | 1/15 |
| Payment authored negatives in that prefix | reference | 1/5 | 1/5 |

These prefix rates are not full-corpus rates. The completed baseline payment own false-pass rate is 0/50. Baseline payment raw/normalized field exact is 492/910 (54.07%); reference is 765/845 (90.53%). Corresponding complete after accuracy is unavailable because the safety gate stopped the run.

## Other verification and disposition

Four regression groups passed: engine 1,584 / 3 skips; backend 1,314; 18 scenario modules / 1,885 counted checks / zero failures; frontend lint/build exit zero. New focused tests: 67 pass. These results do not override the failed false-pass gate. Existing tests/fixture providers, period handling, other extractors and verdict rules remain unchanged.

See measurement-stop.json for value-free numeric evidence, validation.md/results for checks, and diff-stat-main.txt for the tracked-file diff. Newly added files remain untracked and are not included in the literal main-relative diff stat. No private document was remeasured; dumps remain ignored/untracked.

Await user direction before further cause isolation or repair planning. This is not ready for commit approval. No automatic rollback was performed, preserving the reviewable working tree and evidence.
