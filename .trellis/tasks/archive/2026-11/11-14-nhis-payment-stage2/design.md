# NHIS_PAYMENT stage 2 design — approved

## Boundary and evidence

One task owns the payment parser changes and their shared end-to-end safety gate. Separate cause-sized patches/tests provide independent verification; splitting tasks would duplicate the same arithmetic, adapter and measurement review. [Research](research/findings.md) distinguishes demonstrated layout mechanisms from unobservable numeric content.

Runtime changes are limited to `engine_v2/extractors/nhis_payment_gov.py` and payment-only private helpers if necessary. Keep shared `nhis_forms`, OCR adapters/models, preprocessing, LocalOcr, upload rules and other extractors unchanged. Do not change `batch_assess` own-only top-level verdict policy. Do not change dump schema/masking/diagnostics or replay masked words as original evidence. Add synthetic regression modules and a brief explanation in the existing payment-tool documentation.

## C1: explicit adjustment row

Before assigning body words to month bands, identify at most one explicitly labeled `연말정산` row between the twelfth month and the observed sum. Use the existing observed column corridors and relative row pitch; require all row words to be accounted for in bounded cells and complete label evidence exactly matching a fixed constant. Uncertain presence retains review. Unknown/duplicate/misplaced/overlapping extra rows remain structural failures. No word is discarded for being low confidence.

Separate its values from the twelve monthly rows. Validate required printed billed/paid health/care cells and optional outside-income cells with the existing grammar/correction rules. Keep unprinted optional cells null. Do not use an adjustment to fill any monthly cell or compute monthly premium averages. Validate each printed column total against monthly values plus its observed adjustment and validate the paid grand total. Any unknown, negative unsupported value, partial required cell, low-confidence absence evidence or mismatch retains the existing review path. Never assume an unreadable adjustment is zero.

Preserve existing monthly field meanings. Keep adjustment evidence internal to the payment reader and use it only in table arithmetic; introduce no public field or new eligibility input in this task. No cached-row migration is planned.

## C2: component-band clipping

Replace the demand for a clear top-edge gap between group labels and every component fragment with a payment-only selection based on observed group/component roles and vertical center placement. Retain whole original observations. Apply only when exactly one complete supported assignment exists; otherwise retain the original failure path. Require the same complete ordered nine columns, two aligned groups, table boundary and no competing/unaccounted header fragments. Do not allow metadata or footer prose to supply headings. Missing/deleted fragments must continue to fail.

## C3: neighboring component clusters

Keep the current successful path first. When proximity grouping fuses adjacent headings, consider subdivision only if independently observed persistent empty body corridors and complete expected header spellings yield **one** ordered nine-column assignment. Assign whole header fragments in a comparison view; never synthesize a narrower value bbox. Preserve eight component meanings and group alignment. Reject competing assignments, truly merged multi-column observations without reliable separation, deleted/extra/swapped headings and ambiguous body corridors.

Do not change the shared clustering/corridor tolerance. If a conservative unique decomposition cannot be demonstrated with positive and adversarial synthetic cases, defer C3 and report it separately; that does not authorize a broader fallback.

## C4: period and route contracts retained

Keep `payment_period.collect` and `_check_billing_months` behavior. Out-of-range positive/unreadable values, ambiguous periods and unreliable zero corrections retain NEEDS_REVIEW. Correcting table structure may restore the existing arithmetic-backed zero normalization; it must not bypass that gate. Do not infer periods from twelve months, discard competing evidence, or widen date grammar based on these dumps.

Retain current reader selection in this change. Add tests showing why shorter month boxes can choose legacy and why billing cause NONE is not PASS. Do not fallback from a recognized but incomplete government form into legacy. Add tests that normal text upload uses text words, forced batch uses own words, reference output is not merged, and both paths preserve their own conflicts. Documentation explains the intentional difference without changing execution policy.

## Compatibility and failure handling

No existing test expectation is pre-approved to change. New test modules should use independently authored coordinates/values and the existing fictitious fixture helpers without modifying those providers. If any old expected reader, field, validation, digest or verdict changes, stop before editing the assertion and seek approval with file/test/before/after/reason. A regression must be fixed, not hidden by updating expectations.

Keep incomplete structure/confidence caps, numeric corrections, all eight column equations, paid grand total, identity/issue checks and income evidence suppression. Preserve legacy behavior for unrecognized forms. No guarantee is made that any masked real sample becomes PASS: several have other independent failures and their hidden values are unavailable.

## Rollout and rollback

Implement C1–C3 separately with their own failing-then-passing synthetic tests, allowing individual rollback. No production rerun, commit, deployment or migration in the planning phase. Measure the unchanged synthetic v2 corpus before runtime edits and again after final code. An increased negative-case PASS in any compared slice or any newly passing negative case stops work for reporting. Final full verification and a main-relative diff precede separate commit approval. Real selected-case measurement is user-operated only.

## Superseding paging review

Header-edge recovery is held after isolated false-pass reproduction. Settlement and neighbor fusion remain active. New independent paging architecture is proposed in paging-design.md and requires fresh user approval; the previous structural approval does not authorize implementing that guard. No earlier full verification overrides the failed safety gate.
