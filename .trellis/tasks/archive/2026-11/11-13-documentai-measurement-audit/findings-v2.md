# V2 findings and approval handoff

410 distinct logical pairs /820 retained stage evaluations completed with no execution errors. Each of82 applicable type/condition cells contains five different submitted input hashes. The original run took611.18seconds; ten unchanged qualification negative inputs were replayed in13.60seconds after correcting request-date GT, not pooled as extra samples. All original layouts and purpose markings remain unchanged.

## Original baseline, n=5 per type

| Type | A type | B type | A raw/norm exact | B raw/norm exact | A/B unextracted | B raw/norm CER | B s/page |
|---|---:|---:|---|---|---:|---|---:|
| resident_abstract | 5/5 | 5/5 | 35/35 / 35/35 | 35/35 / 35/35 | 0/0 | 0.0000/0.0000 | 1.0837 |
| nhis_payment | 5/5 | 5/5 | 65/65 / 65/65 | 45/65 / 45/65 | 0/0 | 0.7692/0.7368 | 2.1861 |
| nhis_qualification | 5/5 | 5/5 | 35/35 / 35/35 | 35/35 / 35/35 | 0/0 | 0.0000/0.0000 | 1.0978 |
| nhis_acquisition_loss | 5/5 | 5/5 | 30/30 / 30/30 | 30/30 / 30/30 | 0/0 | 0.0000/0.0000 | 1.0058 |
| insurance_4 | 0/5 | 0/5 | N/A (not called) | N/A (not called) | 25/25 | N/A | 1.4254 |

A-called baseline fields are165/165 correct; own145/165=87.88%, with25 fields unextracted in both due insurance classification. Raw and normalized exact figures are identical; formatting-only recoveries are zero. Authored-field correct coverage is145/190=76.32%, numerically equal to v1 original29/38=76.32%. Thus conditional87.88% is a denominator change, not an operational improvement.

## Per-document contribution, original plus stress (35 cases/type)

Counts below are normalized; raw-error/loss counts are identical in this corpus. Wrong/missing called fields and classification-gated unextracted fields remain distinct.

| Type | A type errors (cases) | A field errors | A unextracted | OCR type losses | OCR field losses | Newly called errors | Type/field recoveries | Hidden A errors | Own s/page |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| resident_abstract | 12 | 40 | 84 | 0 | 0 | 24 | 7/0 | 0 | 1.0655 |
| nhis_payment | 15 | 60 | 195 | 0 | 58 | 120 | 10/10 | 0 | 2.2263 |
| nhis_qualification | 11 | 54 | 77 | 0 | 0 | 36 | 6/5 | 0 | 1.1520 |
| nhis_acquisition_loss | 0 | 105 | 0 | 5 | 0 | 0 | 0/0 | 30 | 1.0624 |
| insurance_4 | 35 | 0 | 175 | 0 | 0 | 0 | 0/0 | 0 | 1.4847 |

In these readable expected-valid groups, A wrong fields259 and B wrong fields452 differ by193. The complete decomposition is58 OCR-added field losses +180 newly called errors −15 field recoveries −30 A errors hidden by B classification failure =193. Newly called errors were not observable as field errors in A; they must not all be relabeled intrinsic OCR losses. Classification likewise reconciles73 A failures +5 OCR losses −23 recoveries =55 B failures. These are paired operational effects including segmentation/bounds/confidence, not glyph-only causal attribution.

## Groupwise verdicts, own stage

| Group | n | False reject | False pass | PASS/review/FAIL | s/page |
|---|---:|---|---|---|---:|
| normal_baseline | 25 | 0/25 | N/A | 10/15/0 | 1.3598 |
| stress | 150 | 0/150 | N/A | 20/130/0 | 1.4046 |
| quality_defect | 75 | N/A | 0/75 | 0/25/50 | 0.7251 |
| content_defect | 160 | N/A | 0/160 | 0/80/80 | 1.3554 |

Reference A false-pass results are15/75 quality negatives (blurred payment/qualification/acquisition) and5/160 content negatives (payment missing-page claim). Own sends those cases to review rather than PASS. These counterfactual results identify policy/source-evidence limitations; zero own false-pass must not be described as perfect automatic defect detection. The quality cohort has50 FAIL and25 review; content negatives80 FAIL and80 review.

## Weaknesses and candidates only

1. Insurance classification/source-layout interaction: all35 expected-valid cases fail in A and B, with175 fields unextracted on each side. Retain purpose text/proximity; investigate routing/token-order robustness against independent synthetic variants before any operating change.
2. Payment extraction after own OCR:58 additional field losses (20 on original,20 monochrome,18 layout stress) while A-correct fields were available. Inspect header segmentation/column bounds and retained completeness validations. No amount parser or threshold was changed.
3. Rotation/perspective structure: 90degree own classification0/25,190 unextracted fields; A classification5/25 and own loss5 cases are acquisition. Phone conditional own field accuracy26/165=15.76%; +5degree35/165=21.21%; −5degree40/165=24.24%. StageA is also weak for these geometries, so avoid attributing all losses to recognition.
4. Opportunity changes matter: own recovers23 classification cases but180 fields newly reaching extraction are wrong; report them alongside41 newly called correct fields and15 field recoveries, rather than comparing conditional percentages as a causal delta.
5. Improve corpus breadth only as a future explicitly scoped measurement task: five unique identities/dates still share one source family/font per type. No real-document generalization or population confidence follows.
6. Separate quality/paging automatic detection from manual review: preserve and inspect the A-only false-pass negatives above; do not fix decision rules within this measurement task.

## Review artifacts

- [Full paired table](measurement-v2-n5-final.md): all condition/field raw+normalized figures, A/B timings and code/group rates.
- [Source evidence](source-decisions.md): conservative retention and every parameter/truth correction.
- [Validation](validation-v2.md): complete regressions and Git review state.

No OCR, classifier, extractor, adapter, verdict or existing test was changed. Prior reports and initial/intermediate numeric snapshots remain preserved. Final user approval is pending; no new commits or remote/main operations have been performed.
