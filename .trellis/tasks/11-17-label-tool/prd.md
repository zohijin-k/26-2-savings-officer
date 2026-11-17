# Label review tool

## Goal

Localhost-only blind labeling tool so Jin can record ground-truth document states on the Mac for
B1-B3 (re-upload accuracy) and C1-C3 (false pass) defined in
`.trellis/tasks/11-17-speed-baseline/measurement-definitions.md`, using label criteria v0.1.
Development and tests on this machine use synthetic documents only.

## Requirements

- Input: doc_timing `rows.jsonl` (row format 2+), `--root` PDF folder, `--out` label folder outside the repository.
- Samples: B = every FAIL document; C = PASS documents stratified by form, default 150, fixed seed;
  sample list and seed saved in the out folder; reruns give the same sample.
- Cross-check: 20 already-labeled documents (fixed seed) labeled again blind.
- New rows (later run): labels are reused per document key; only new FAIL / new C sample members need labels.
- Screen: page images (PyMuPDF), zoom, page navigation, ordinal only (no file names/paths).
  Stage 1 blind state (PASS / NEEDS_REVIEW / FAIL / HOLD) with R1-R6, R9 for FAIL; keyboard shortcuts;
  issue-date cutoff from engine rules. Stage 2 (after stage 1 saved): engine decision and reason codes;
  PASS sample shows recomputed key values (service path, own, JBAI/Upstage off) with per-item O/X, never saved.
  Progress, go back and fix, stop and resume.
- Labels file stores key, stage, state code, reason codes, item O/X, time, criteria version only.
- Summary: B1/B2/B3 and C1/C2/C3 (Clopper-Pearson one-sided 95%), HOLD excluded and HOLD as wrong,
  NEEDS_REVIEW PASS count, per-form and per-reason counts, cross-check agreement. Numbers and codes only.
- Security: 127.0.0.1 only (no option), no external resources, keys only from rows, no traversal/symlinks,
  no paths/names/values in logs.

## Acceptance Criteria

- [ ] `engine_v2/tools/label_review.py` + static screen files in the repository.
- [ ] Tests: sample reproducibility, blind ordering, value/path/memo-free storage, traversal rejection,
      127.0.0.1 fixed, Clopper-Pearson (0, 1, many), two HOLD treatments, additional-label merge,
      cross-check agreement.
- [ ] `engine_v2/tests` full suite passes with no expectation changes.
- [ ] No operating code (demo/backend, engine_v2 classification/extraction/verdict) changed.
