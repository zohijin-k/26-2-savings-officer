# Stage-2 verification and commit gate

## Final four-group verification

| Group | Main reference | Final |
| --- | --- | --- |
| engine_v2 pytest | 1,535 passed / 3 skipped; independently rerun before changes | **1,584 passed / 3 skipped / 0 failed** (+49 new cases) |
| demo/backend pytest | 1,296 passed | **1,314 passed / 0 failed** (+18 new cases) |
| scenarios | 18 modules / 1,885 counted checks / 0 failures | **18 exits zero / 1,885 counted checks / 0 failures** |
| frontend | lint/build | **Both exit 0**; existing large-chunk build advisory |

P14 validates eight templates/geometry/rendering as an aggregate and does not provide a numeric assertion counter. The other seventeen modules account for the 1,885 checks. Per-module exits/counts are in validation-results.json. No live/remote flags were used. Newly generated synthetic sample files, isolated DB/storage and contained temporary directories were used; no private source documents or private batch outputs were opened.

All existing test files and fixture providers are byte-identical to their starting hashes. **Existing expectation-change inventory: empty.** The only runtime file changed is `engine_v2/extractors/nhis_payment_gov.py`; the period collector, reader-selection function, other extractors/adapters/rules, benchmark generator/truth/metrics and dump masking implementation are unchanged. The final runtime in the verification mirror matches the primary checkout. Python syntax, git diff hygiene and Trellis context validation pass; no configured Python type-check command exists.

## Red/green cause evidence

The first 63 finalized new cases were rerun against a separate pristine tracked-source copy, yielding **22 expected positive regression failures / 41 passing guards**. Exactly those three shape families plus actual uploads turn green after repair. Four additional missing-month/complete-table conflict guards bring final focused coverage to **67 passed**.

| Cause | Before | After | Retained limits |
| --- | --- | --- | --- |
| Extra adjustment row | 13 shape cases fail; extra row contaminates the last month and every column sum | 13 pass; bounded exact-label adjustment contributes to totals only | Unknown/duplicate/misplaced/incomplete/uncertain row remains review; nonzero adjustment never changes monthly values or averages |
| Group-edge clipping | 3 scale cases fail component/column checks | 3 pass with complete ordered evidence | Missing/extra/swapped/conflicting/uncertain added fragments remain unresolved |
| Neighbor proximity fusion | 3 scale cases fail component/column checks | 3 pass only with unique complete labels and body corridors | Empty/ambiguous corridors, merged observations and damaged labels remain unresolved |
| End-to-end uploads | 3 synthetic shape uploads are NEEDS_REVIEW | 3 become PASS with their full valid evidence | Unknown adjustment labels and independent conflicts remain NEEDS_REVIEW |

C1 alone: 29 related cases pass. C1+C2: 37 pass. Final shape/route/safety coverage: 67 pass. The fused positive fixture was refined to include the eight printed body columns required by the demonstrated shape; the initial empty-optional version remains a negative. No existing fixture or measurement source was tuned. See review.md.

## Scope of fixes and deferred causes

Fixed the reproduced structural row assignment, header-band clipping and uniquely resolvable proximity fusion. Added normal-text versus forced-batch routing tests and explanatory documentation. Did not change period conflict/unreadable handling, infer zeros, suppress out-of-range positives, improve OCR numeric recognition, remove ambiguous body artifacts, change reader selection or route failed government forms through legacy.

These are synthetic reproductions and code fixes, not a claim that any particular private case now passes. The masked adjustment label, underlying digits and independent remaining failures are unavailable. Real selected-case reassessment remains user-operated with `batch_assess --ids`.

## Measurement status

FAILED: work stopped under the user condition. The baseline completed 410 pairs without execution errors. After 29 matched pairs, own newly passed the authored negative s1_nhis_payment_pages_incomplete (NEEDS_REVIEW to PASS). The monitor terminated measurement immediately. Complete after accuracy is unavailable. See measurement-stop.md/json. Passing regressions do not override this gate.

## Validation environment corrections

An initial baseline measurement and concurrent test attempts exhausted disk space because completed pytest temporary uploads accumulated. These attempts are excluded from acceptance evidence. Only taAPI-key-prefixcreated synthetic directories were removed; retries use an external-to-source pytest teardown hook that removes taAPI-key-prefixowned function temporary directories after teardown. Existing assertions are unchanged.

One completed backend attempt had 1 environmental failure / 1,313 passes because the isolated source copy lacked the installed frontend TypeScript dependencies. Linking that copy to the repository's existing node_modules and rerunning the same complete suite produced 1,314 passes. No installation or product/test expectation change was used. No interrupted run is reported as a successful gate.

## Proposed commit

Not ready for approval because the false-pass gate failed. The earlier proposed grouping, preserved for review only, was:

`fix(payment): separate settlement amounts and recover proven headers`

- `engine_v2/extractors/nhis_payment_gov.py`
- `engine_v2/tests/payment_stage2_samples.py`
- `engine_v2/tests/test_payment_stage2_structure.py`
- `demo/backend/tests/test_payment_stage2_routes.py`
- `engine_v2/docs/payment-structure-dump.md`
- `.trellis/spec/backend/document-form-contracts.md`
- This task's planning/research/review/value-free verification artifacts

No unrecognized pre-existing dirty files were present. Exclude every ignored dump, generated synthetic source/image/log, model/dependency asset and validation sandbox. No staging, commit, push, merge, task archive or journal commit has occurred.
