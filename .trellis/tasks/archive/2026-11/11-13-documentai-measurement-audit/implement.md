# Approved execution

User approved implementation/n=5 with conservative source constraints. Final results are gated on another user approval.

- [x] Reaggregate saved originals and inspect implementation.
- [x] Replay 35 synthetic image cases with observation-only wrappers; verify every saved field result reproduces.
- [x] Inspect embedded fonts/glyphs and synthetic image crops; cross-render insurance with Poppler.
- [x] Run perfect-text/geometry and truth-selected-extractor diagnostic controls, separate from official metrics.
- [x] Count symmetric format-only mismatches and derive quality-defect reaggregation.
- [x] Prepare evidence report and concrete scoped plan.
- [x] Obtain user approval.
- [x] Implement conservative source retention, metric layers, normalization and case taxonomy; add new tests without changing existing tests.
- [x] Confirm unchanged source geometry/labels/font coverage, paired reader contracts and five unique source/input checks.
- [x] Execute n=5 (175 original matrix images + 25 explicit layout-stress images + 210 existing defect counterparts = 410 total pairs).
- [x] Run 61 new focused tests and all four regression branches; final engine1,375/3, backend1,252, scenarios18/1,885/0 and frontend lint/build pass.
- [x] Record separate final report, findings and S01–S08 decisions; preserve old reports and initial/intermediate snapshots.
- [x] User approved the reviewed local commit batches with `commit apply`.
- [x] Apply local work/report commits and archive the task. The developer workspace journal records the completed session.

Estimated runtime only: original-only 25 images approximately 40–60 seconds; complete 175-image condition matrix approximately 5–7 minutes; complete 385-case suite approximately 10–15 minutes on this Mac, excluding implementation and validation time. These are extrapolations, not completed n=5 results.
