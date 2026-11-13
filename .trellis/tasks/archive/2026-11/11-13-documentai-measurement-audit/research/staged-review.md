# Independent staged measurement review

Scope: new corpus, staged observation/normalization, aggregation/report and new tests. No real/private document was accessed. No production code, prior measurement/report or existing test was edited. No commit was made.

## Contracts reviewed

- Original geometry, font sizes, cell counts and purpose markings remain intact. Fictitious name/issue-date values create five distinct authored parameter sets; the corpus explicitly discloses the shared layout/font family.
- Insurance output date preserves the existing fixture's issue-plus-one-day relationship. Negative issue truth follows the actually printed varied date; no guessed field value is inserted into extraction.
- Reference words come from the generated text layer and their four-corner bounds follow the same scale, expanded rotation or phone homography as the image. `layout_variant` is a separate stress augmentation retaining all source characters.
- Reference and own stages go through the same image upload reader, metadata, classification, extraction and verdict path. Reference confidence is one; differences include segmentation, boxes and confidence as well as recognition. This is operational paired attribution, not a glyph-only causal estimate.
- Actual source type and expected upload slot are separate, so wrong-slot defects affect verdict without corrupting independent type/field truth.
- An uncalled source-type extractor yields `UNEXTRACTED_CLASSIFICATION` with null exact/CER metrics. Called-but-missing fields remain errors. Swallowed dependency/extractor exceptions are execution errors, not classification misses.
- Raw typed semantic equality is preserved. Symmetric field-aware normalization handles Unicode width, whitespace, validated dates, numeric grouped commas and dash equivalents, while preserving identifier zeros, meaningful address hyphens, missing/empty distinction and list order.
- Group expectations are authored before observing verdicts. Original normal, expected-valid stress, designed quality negatives and content negatives have separate false-reject/false-pass denominators. Review is shown separately. No applicable population is reported as N/A, not a misleading zero rate.
- Paired losses/recoveries distinguish A classification failure, A called-field error, A-correct/B-lost field, newly gated B field and B recovery. Signed deltas are explicitly not treated as all introduced errors when called populations change.
- Public stage/report projection uses fixed names/states/codes and metrics, not extracted values or dependency exception details. Existing quiet/read-only protections are reused, with scoped wrappers restored after measurement.

## Findings and resolution

| ID | Finding | Resolution |
|---|---|---|
| R01 | Unreadable inputs initially used identical invalid bytes for every sample, despite distinct original source fingerprints. | Root added generic document/sample suffixes, actual submitted-input SHA uniqueness checks per type/condition and retained input fingerprints. No invalidity or production behavior changed. |
| R02 | Opening design text still proposed eliminating ambiguous purpose/title collision, contrary to the final user constraint; detailed source evidence was not directly rendered in generic report text. | Root repaired the superseded design and added source-decisions.md S01–S07; final report is to append explicit evidence. Original layout stays intact. |
| R03 | A `.md` JSON-output path would alias its sibling report and overwrite the new JSON. | Root requires `.json` suffix before work and checks prior JSON/report/checkpoint outputs. Existing reports remain protected. |
| R04 | Mixed content-defect aggregation includes zero-page invalid-input durations in per-page timing numerator. Per-condition unreadable timing is correctly N/A and normal/stress timings are unaffected. | Report-only refinement requested: separate page and nonpage time; saved rows permit recomputation without repeating measurement. Root and report owner notified. |

## Validation

- First independent focused run of the three new test files: 52 passed, five existing PyMuPDF warnings, 3.01 seconds.
- Repeated independent run after R01–R03 fixes: **53 passed**, five existing PyMuPDF warnings, 3.38 seconds.
- Source/case counts checked from corpus structure: 25 original normal +150 stress +75 quality defects +160 content negatives =410 paired cases /820 stage evaluations. The runner enforces submitted-input uniqueness per type/condition and targets five; root will verify the completed artifact. Special missing-address/month conditions apply only to their relevant type.
- No n=5 model run was launched by the reviewer. Root owns expensive run, final aggregate arithmetic and all four full regression branches. Avoid concurrent model work while measuring timing.

Final user approval remains required before the requested next action. This review does not authorize production changes, remote Git actions or replacing the previous report.

## Final report-only resolution

R04 was resolved in the report module: page_seconds sums only rows with physical pages; nonpage_seconds and nonpage_attempts remain separate. Mixed-content per-page rates no longer include malformed-file duration. Two added tests cover mixed zero-page timing and source-evidence rendering; report owner's final suite is19 passed. Root will regenerate summary/Markdown from the completed pair rows to apply this report-only correction without repeating OCR.

Root also added explicit corpus tests for output-extension alias rejection, five distinct submitted invalid inputs and duplicate submitted bitmap rejection. Original-layout/font-size/cell-count checks and purpose retention remain unchanged.
