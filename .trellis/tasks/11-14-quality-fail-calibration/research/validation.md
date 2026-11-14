# Final verification evidence

## Full before and after verification

| Branch | Before | Final after | Delta |
| --- | --- | --- | --- |
| engine_v2 pytest | 1,448 passed, 3 skipped | 1,448 passed, 3 skipped | 0 |
| demo/backend pytest | 1,252 passed | 1,296 passed | +44 new parity cases |
| Backend scenarios | 18 modules, 1,885 counted checks, zero failures | 18 modules, 1,885 counted checks, zero failures | 0 |
| Frontend npm test | 9 passed | 9 passed | 0 |
| Frontend lint/build | Passed | Passed | Existing large-chunk build warning |

All commands completed with exit 0 against the final frozen source. The existing frontend build warning concerns a chunk above 500kB. Dependency deprecation warnings also occur in the unchanged baseline. The full frozen source hash check passed after final measurement.

## Scenario detail

| Module | Before counted checks | Final counted checks | Failures |
| --- | --- | --- | --- |
| run_p2_scenarios | 53 | 53 | 0 |
| run_p3_scenarios | 186 | 186 | 0 |
| run_p4_scenarios | 189 | 189 | 0 |
| run_p5_scenarios | 152 | 152 | 0 |
| run_p6_scenarios | 261 | 261 | 0 |
| run_p7_scenarios | 253 | 253 | 0 |
| run_p8_localocr_scenarios | 89 | 89 | 0 |
| run_p9_identity_scenarios | 98 | 98 | 0 |
| run_p11_criteria_scenarios | 38 | 38 | 0 |
| run_p12_subsidy_criteria_scenarios | 29 | 29 | 0 |
| run_p13_household_scenarios | 26 | 26 | 0 |
| run_p14_pdf_forms_scenarios | 8-template validation | 8-template validation | 0 |
| run_p15_jbai_scenarios | 129 | 129 | 0 |
| run_p16_job_docs_scenarios | 96 | 96 | 0 |
| run_p17_own_scenarios | 75 | 75 | 0 |
| run_p18_applicant_precheck_scenarios | 180 | 180 | 0 |
| run_p19_nhis_history_scenarios | 24 | 24 | 0 |
| run_p20_nhis_continuation_scenarios | 7 | 7 | 0 |

P14 emits one successful aggregate result for eight templates and their coordinate/rendering checks. The other 17 modules report 1,885 counted checks.

## Existing expectation audit

An AST comparison against main confirms exactly four existing test functions changed and all existing test-function membership remains. The P18 quality helper also received its approved review-oriented rename and assertions. The exact before/after expectations and reasons are recorded in test-impact.md.

- `demo/backend/tests/run_p18_applicant_precheck_scenarios.py` / `test_uncertainty`
- `demo/backend/tests/test_nhis_recent_history.py` / `test_short_explicit_period_is_fail_only_when_readable`
- `demo/backend/tests/test_quality_failure_policy.py` / `test_quality_fail_survives_confidence_and_every_early_return`
- `demo/backend/tests/test_quality_failure_policy.py` / `test_nhis_identity_review_cannot_downgrade_measured_quality`

## Review and supported-input correction

The initial implementation passed 199 focused tests and its first independent check passed 290. Further parent diagnostics used the actual JOB_PACKAGE certificate checklist and found that an accepted transcript alternative could upload as NEEDS_REVIEW but submit as WRONG_DOCUMENT_TYPE FAIL. A duplicate type could also hide a low-quality document. The first complete intermediate measurement had zero new defect PASS and matching field metrics. That evidence remains temporary.

The correction preserves actual detected types, handles accepted alternatives with explicit quality-review evidence, and aggregates every explicit quality context across duplicate documents. Twenty extra cases brought the parity file to 44 cases. The implementer passed 219 focused tests. The final independent Trellis check passed 310 focused tests and found no issue requiring another change. Both checks reviewed the policy spec. Final full verification and a fresh final v2 run followed the correction.

## Final synthetic v2 result

Before and final after each completed 410 pairs with zero execution errors. Inputs, sources, dependency/model hashes and classification/extraction metrics match. New defect PASS cases and increased false-acceptance slices are zero across 250 comparison slices. Forty reference A and five own B case-stage outcomes changed from FAIL to NEEDS_REVIEW. Detailed denominators, status distributions and changed cases are in measurement-comparison.md.

## Approval state

Implementation and the corrected four-function old-expectation inventory were authorized. The pre-commit report includes the main-relative diff, full verification table and synthetic comparison. Commit approval is pending.
