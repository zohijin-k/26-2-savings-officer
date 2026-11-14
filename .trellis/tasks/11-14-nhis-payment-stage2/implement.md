# Implementation and review plan — approved

## Approval gates

- [x] User approved task creation/research, new branch and private-evidence limits.
- [x] Created branch `work/nhis-payment-stage2`; started task after implementation approval.
- [x] Investigated all four questions and performed transient synthetic probes.
- [x] User approved implementation on 2026-11-14 with six explicit safety/verification conditions.
- [x] Ran `task.py start`; loaded before-development/check/spec guidance and implemented the approved payment-only changes.
- [ ] Any existing expectation change requires a separate exact inventory and approval **before editing the assertion**.
- [ ] Commit only after the final evidence/commit plan receives explicit approval.

## Ordered work

1. Capture pristine source/test/fixture/tool fingerprints and the approved changed-file allowlist. Build a fresh isolated synthetic checkout/mirror from tracked repository code plus this task's approved changes; do not copy existing private/document trees. Use only in-repository installed dependencies/assets. Put generated inputs, temporary data, pytest bases and measurement outputs in a new owned ignored directory inside the repository; do not open external document paths. Inspect test entry points for private/default fixture access before running them. No remote/live flags or model downloads.
2. Run **before** synthetic v2 with samples=5, seed=20261113 and a fresh output. Freeze generator/truth/metrics and inputs. The historical measurement is context, not a substitute for this baseline. Save only value-free metrics in review artifacts; keep generated inputs ignored. Keep that baseline mirror frozen until complete and usable. Development in the separate primary checkout may proceed concurrently without updating the frozen mirror; compare only after both measurements complete. This execution-order refinement does not change the approved behavior or validation gates.
3. Add new permanent synthetic tests (suggested `engine_v2/tests/test_payment_stage2_structure.py`, `demo/backend/tests/test_payment_stage2_routes.py`). Coordinates must be newly authored from relative layout shapes, never copied from the masked dumps. Independent values must balance by construction; deliberately corrupt one cause at a time. No private dump import/glob/fixture dependency.
4. C1: first reproduce adjustment-row contamination without digit errors. Then implement exact-label bounded adjustment handling. Prove twelve monthly rows, eight component sums, paid grand total and unchanged monthly averages; test zero/nonzero adjustments and observed optional blanks. Reject unknown label, duplicate/misplaced row, partial required cells, crossing word, unknown glyph, unsupported negative value, one-unit sum error and invalid grand total. Keep review for unrelated identity/date/period defects. Do not change aggregate assertions merely to make one sample pass.
5. C2: first reproduce two upper header fragments clipped by the group lower edge. Implement payment-only comparison selection. Positive tests vary scale, small vertical displacement and token splitting. Negative tests delete fragments or introduce competing metadata/header/footer observations. Keep whole boxes and every amount guard.
6. C3: first reproduce a care/next-component proximity cluster fusion while body corridors remain clear. Implement only unique full-label/corridor-backed decomposition in the payment reader. Test expansions, splitting and scale alongside ambiguous corridor, true merged observation, swapped labels, duplicate/extra label and deleted label negatives. If safely unresolved, leave it in review and report as deferred rather than weakening invariants.
7. C4: add period/route tests and scoped documentation. Prove intact/split period tokens, unsupported punctuation, low-confidence range, outside positive, unknown outside value, arithmetic-backed zero correction and correction with broken arithmetic. Prove shorter month boxes change current routing; NONE billing cause plus failed validation remains review. With authored PDFs and deterministic fake provider words, prove normal text upload does not invoke own, forced batch does, reference and own disagree without merging, and a valid text map cannot override own's conflict in batch. Preserve partial-text routing and attachment scoping. Add an actual synthetic TestClient upload for changed payment shapes where appropriate. Do not change `read_document`, verdict rules or batch policy.
8. Run focused new/related tests after each cause. Preserve existing tests and fixture providers byte-for-byte unless a separately approved expectation change is required. Review NHIS_PAYMENT-only runtime diff and income/identity/confidence propagation. Record fixed/deferred causes separately.
9. Freeze final source and run **after** the identical full v2 command at a new destination. Compare all case keys, input fingerprints, source/dependency/model identities, called/unextracted/error denominators, payment field exact/CER and negative-case PASS. Require no newly passing negative case and no increase in false-accept count/rate in any comparable A/B × type × group × condition slice, including all-document slices. Stop and report an increase even if another slice improves. Do not tune the corpus or expected verdicts. If inputs differ, investigate before claiming a comparison.
10. Run final four-group verification, frontend checks and diff hygiene on the final frozen source. Review/update applicable payment specs with lessons, without modifying unrelated rules. If code changes after measurement/checks, rerun affected evidence and the final measurement as necessary.
11. Present main-relative diff, all actual verification counts, measurements, cause disposition, existing-expectation inventory (ideally empty), dirty-file list and proposed commit grouping. Wait for explicit approval. Do not stage dumps, commit, push, archive or auto-commit a journal while waiting. User performs selected private batch measurement with `batch_assess --ids`.

## Validation commands and denominators

Run from the new synthetic source mirror where applicable, using the repository virtual environment. `NEW_RUN_DIR` below means a newly created owned ignored directory, not an existing private path. Keep TMPDIR and test storage in that directory. Inspect scenario imports/default data access before execution; synthesize fresh fixture inputs needed by tests rather than opening existing private data.

```sh
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output NEW_RUN_DIR/before.json
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests/test_payment_stage2_structure.py demo/backend/tests/test_payment_stage2_routes.py -q --basetemp NEW_RUN_DIR/focused
PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output NEW_RUN_DIR/after.json
PYTHONPATH=. .venv/bin/python -B -m pytest engine_v2/tests -q --basetemp NEW_RUN_DIR/engine
PYTHONPATH=. .venv/bin/python -B -m pytest demo/backend/tests -q --basetemp NEW_RUN_DIR/backend
```

Execute all 18 tracked `demo.backend.tests.run_p*_scenarios` modules sequentially without live/remote options. P14 has an exit-verified eight-template aggregate rather than an invented numeric count. Run `npm run lint` and `npm run build` under `demo/frontend`. Use `git diff --check`, changed-Python syntax checks, `task.py validate`, and `git diff --stat main` plus untracked new-file inventory. No configured Python type check exists; do not relabel syntax checks as type checking.

| Gate | Prior main reference; must rerun after implementation |
| --- | --- |
| engine_v2 | 1,535 passed / 3 skipped; final adds new tests, preserves old membership |
| demo/backend | 1,296 passed; final adds new tests |
| scenarios | 18 modules / 1,885 counted checks / 0 failures |
| frontend | lint and build pass |

V2: n=5 produces 410 pairs / 820 stage evaluations across all five document types. Report payment slices separately with raw and normalized exact numerators/denominators, CER, missing/unextracted/errors and per-field results. Show expected-valid baseline/stress separately from quality/content negatives. False pass means PASS on an authored negative case; NEEDS_REVIEW never counts as PASS. Do not conflate the old nonzero reference-stage false passes with newly introduced ones or assert a zero baseline without measuring it.

## Current status

STOPPED: one new own false PASS on s1_nhis_payment_pages_incomplete after 29 matched after pairs. The monitor terminated measurement. No further implementation or measurement proceeds pending user direction. Baseline completed 410 pairs without execution errors. See measurement-stop.md/json. New focused cases (49 engine / 18 backend) and all four regression groups passed, but do not override the failed gate. All old tests/fixtures and period handling remain unchanged. DiAPI-key-prefixfull attempts are excluded. Not ready for commit approval; working tree remains uncommitted.

## Authorized follow-up and current phase

Stages 1–2 investigation and stage 3 proposal were reported separately, then stage 4 held only header-edge recovery. Retained focused suite: 57 pass / 10 deferred. See paging-investigation.md and paging-design.md. Task is planning; do not implement paging or restore the held recovery until approval. Stage 5 adds false-rejection nonincrease to the full 410-pair gate before any future commit request.


## Latest state — supersedes historical STOPPED/planning notes above

User approved both-path payment paging implementation and header-edge recovery restoration. The independent guard now makes the unchanged s1 missing-pages input PAGES_INCOMPLETE FAIL in native own and reference. No previous test input/assertion was changed. Strict paging added 26 expectation impacts; user did not approve fixture completion and requested evidence plus an isolated rule review instead.

Current review: `paging-refinement-review.md` records official-source limits, all five masked-dump engine O/X observations, a collector-range omission, and the proposed same-document printed-total/month-coverage waiver. Isolated experiment: 26/26 original cases pass unchanged, remaining impacts 0; 24 additional synthetic controls pass; target both paths still PAGES_INCOMPLETE FAIL. Production has not adopted this proposal. Other-document wiring was audited read-only in `paging-other-documents-audit.md`. Await user review. Do not modify existing inputs, apply the proposal or ask for commit approval from this partial validation. Final implementation still requires the complete original-baseline 410-pair comparison and all four regression groups.

Strict-guard (before proposed refinement) full v2 completed 410 pairs / 820 stages / errors 0; no new false pass/reject; reference existing false passes reduced by 5. This does not validate the pending proposal or collector-range repair. Evidence appended to paging-refinement-review.md.


## Approved execution now

1. Capture new refinement regressions RED; hold only C2. Keep old tests byte-identical.
2. Add payment table evidence and margin-only folio collection; both routes share extraction/conversion/rules. No authoritative split-file aggregation exists, so use user's REVIEW exception, never a false per-file omission FAIL.
3. Add backward-compatible safe batch statistics with synthetic-only tests. Rescan only authorized masked dumps for shape adoption without numeric interpretation or copied coordinates.
4. Run focused GREEN, report existing failures immediately without editing them. Execute unchanged 410-pair comparison with stop-on-new-false-PASS monitor; compare original baseline and strict-guard predecessor separately.
5. Run engine/backend, 18 scenario modules and tsc/oxlint/vite. Review relevant specs; show all impact lists, main diff and staged data/secret hygiene. Wait before commit.


## Final execution state

The later read-only both-repository audit supersedes aggregation-unknown REVIEW: explicit slots retain one replacement file. Implemented reliable printed excess FAIL, preserved nine old FAIL expectations, applied approved19 test adjustments plus ten incomplete controls. The date-boundary and financial-proof fixes have red5/green66 evidence. All interrupted candidates are excluded; final source is frozen under stage2_paging_final_20261115 with a new full410 gate and all four checks. No further runtime edits while final measurement runs. Final original-baseline comparison, source integrity, main stat, staged hygiene and commit approval remain.


## Final gates achieved; commit approval pending

410 pairs/820 stages complete, source metadata/input fingerprints equal original baseline; zero new false PASS/reject and no slice increase. Existing payment reference false PASS10/50->5/50, own0/50 unchanged, new REVIEW transitions0. Four groups: engine1641pass3skip3strictC2xfail; backend1410pass2strictC2xfail; scenarios18/1885/0; tsc/oxlint/vite all pass. Runtime source unchanged from final freeze. See paging-final-validation.md and paging-final-measurement-comparison.md/json. Stage only reviewed code/tests/specs/value-free task artifacts, inspect secret/private/masked paths, show main-relative stat and wait for explicit commit approval. No commit/push/archive yet.
