# DocumentAI paired-stage synthetic measurement v2

Seed: 20261113; distinct samples per type/condition: 5; actual case count: 410.

A = exact generated text-layer words mapped into the same image geometry and fed through the unchanged image reader; B = actual own OCR of that image. Both classify independently and use the same policy, metadata and production extraction/verdict path. A uses perfect recognition/confidence, while B contributes recognition, segmentation, boxes and confidence effects. The difference is a paired operational attribution, not a glyph-only causal experiment.

No original layout was repaired without evidence: ambiguous purpose/title proximity and payment table layout remain, with their failures visible in A. A reference-stage failure is a baseline classification/extraction/source interaction, not an OCR error. No real document or production OCR/classifier/extractor/verdict code was changed. The old report is retained.

Field accuracy is conditional on the expected source-type extractor being called. Called-but-missing fields are errors; UNEXTRACTED_CLASSIFICATION and ERROR are separate outcomes and are excluded from field-accuracy/CER denominators. Raw and normalized exact figures are both shown. Correct-field coverage uses all authored fields and is explicitly not called field accuracy.

Raw CER compares literal semantic-value streams. Normalized CER compares field-aware canonical streams; fixed JSON keys/punctuation and insurance geometry/confidence are excluded. CER is summed edits / max(reference characters, 1), not the mean of field ratios. Empty fields and absent fields remain distinct. List order and identifier zeros are preserved.

Case group and expected VALID/FAIL are authored before observing results. expected=FAIL identifies a negative/defective cohort where PASS is forbidden, not an assertion that every content defect must produce final FAIL: production review policies remain valid and visible. Quality-defect inputs specifically have designed FAIL as the desired quality outcome. Normal baseline, stress, quality defects and content defects have separate verdict populations. Confirmed false rejection requires final FAIL plus an allowlisted FAIL-severity reupload code on expected VALID. False acceptance is PASS on expected FAIL. NEEDS_REVIEW is neither. N/A means no applicable denominator. A low false-accept rate with many reviews is not automatic defect diagnosis.

Timing is processing seconds for physical-page inputs / processed input pages, excluding source generation and metric/report calculations. Total seconds retain all attempts; nonpage attempts and their seconds are accounted separately and cannot enter the per-page numerator. A performs no model inference; B does. Cold initialization may affect the first own page. Malformed input bytes have no physical page throughput interpretation and are shown separately from normal/stress timing.

## Case groups and verdict rates

| Group | Stage | n | Type | Raw / normalized exact | Unextracted | Error fields | Failed cases | Nonpage attempts/seconds | False reject | False pass | PASS/review/FAIL/X | s/page |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal_baseline | A | 25 | 20/25 (80.00%) | 165/165 (100.00%) / 165/165 (100.00%) | 25 | 0 | 0 | 0/0.0000 | 0/25 (0.00%) | 0/0 (N/A) | 15/10/0/0 | 0.1500 |
| normal_baseline | B | 25 | 20/25 (80.00%) | 145/165 (87.88%) / 145/165 (87.88%) | 25 | 0 | 0 | 0/0.0000 | 0/25 (0.00%) | 0/0 (N/A) | 10/15/0/0 | 1.3598 |
| stress | A | 150 | 82/150 (54.67%) | 375/634 (59.15%) / 375/634 (59.15%) | 506 | 0 | 0 | 0/0.0000 | 0/150 (0.00%) | 0/0 (N/A) | 30/120/0/0 | 0.2285 |
| stress | B | 150 | 100/150 (66.67%) | 393/825 (47.64%) / 393/825 (47.64%) | 315 | 0 | 0 | 0/0.0000 | 0/150 (0.00%) | 0/0 (N/A) | 20/130/0/0 | 1.4046 |
| quality_defect | A | 75 | 60/75 (80.00%) | 495/495 (100.00%) / 495/495 (100.00%) | 75 | 0 | 0 | 0/0.0000 | 0/0 (N/A) | 15/75 (20.00%) | 15/10/50/0 | 0.0782 |
| quality_defect | B | 75 | 20/75 (26.67%) | 95/200 (47.50%) / 95/200 (47.50%) | 370 | 0 | 0 | 0/0.0000 | 0/0 (N/A) | 0/75 (0.00%) | 0/25/50/0 | 0.7251 |
| content_defect | A | 160 | 110/160 (68.75%) | 875/925 (94.59%) / 875/925 (94.59%) | 315 | 0 | 0 | 25/0.0513 | 0/0 (N/A) | 5/160 (3.12%) | 5/70/85/0 | 0.1497 |
| content_defect | B | 160 | 110/160 (68.75%) | 775/925 (83.78%) / 775/925 (83.78%) | 315 | 0 | 0 | 25/0.0082 | 0/0 (N/A) | 0/160 (0.00%) | 0/80/80/0 | 1.3554 |

## Original normal baseline by document

| Type | Stage | n | Type correct | Raw / normalized exact | Raw / normalized CER | Called/possible fields | Unextracted | s/page |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resident_abstract | A | 5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000 / 0.0000 | 35/35 | 0 | 0.1459 |
| resident_abstract | B | 5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000 / 0.0000 | 35/35 | 0 | 1.0837 |
| nhis_payment | A | 5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 0.0000 / 0.0000 | 65/65 | 0 | 0.1667 |
| nhis_payment | B | 5 | 5/5 | 45/65 (69.23%) / 45/65 (69.23%) | 0.7692 / 0.7368 | 65/65 | 0 | 2.1861 |
| nhis_qualification | A | 5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000 / 0.0000 | 35/35 | 0 | 0.1477 |
| nhis_qualification | B | 5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000 / 0.0000 | 35/35 | 0 | 1.0978 |
| nhis_acquisition_loss | A | 5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000 / 0.0000 | 30/30 | 0 | 0.1411 |
| nhis_acquisition_loss | B | 5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000 / 0.0000 | 30/30 | 0 | 1.0058 |
| insurance_4 | A | 5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | N/A / N/A | 0/25 | 25 | 0.1485 |
| insurance_4 | B | 5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | N/A / N/A | 0/25 | 25 | 1.4254 |

## Classification/extraction versus OCR contribution by document

This attribution table covers expected-valid normal baseline and stress groups only. Deliberately unreadable/defective inputs are excluded from weakness attribution; their raw paired counts remain in JSON and their stage outcomes remain in the full tables. Reference field errors are A-called fields whose value is wrong or missing; raw/normalized counts are displayed together. Reference unextracted fields are A classification-gated outcomes. OCR field losses require an A-correct field and a B-called wrong/missing field. OCR unextracted losses require an A-correct field and B classification-gated extraction. Recoveries are shown separately; simple signed error differences must not be treated as total introduced errors.

| Type | Group | n | A type errors | A field errors raw/norm | A unextracted | OCR type losses | OCR field losses raw/norm | OCR unextracted raw/norm | Type recoveries | Field recoveries raw/norm | B−A type errors | B−A field errors raw/norm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resident_abstract | normal_baseline | 5 | 0 | 0/0 | 0 | 0 | 0/0 | 0/0 | 0 | 0/0 | 0 | 0/0 |
| resident_abstract | stress | 30 | 12 | 40/40 | 84 | 0 | 0/0 | 0/0 | 7 | 0/0 | -7 | 24/24 |
| nhis_payment | normal_baseline | 5 | 0 | 0/0 | 0 | 0 | 20/20 | 0/0 | 0 | 0/0 | 0 | 20/20 |
| nhis_payment | stress | 30 | 15 | 60/60 | 195 | 0 | 38/38 | 0/0 | 10 | 10/10 | -10 | 148/148 |
| nhis_qualification | normal_baseline | 5 | 0 | 0/0 | 0 | 0 | 0/0 | 0/0 | 0 | 0/0 | 0 | 0/0 |
| nhis_qualification | stress | 30 | 11 | 54/54 | 77 | 0 | 0/0 | 0/0 | 6 | 5/5 | -6 | 31/31 |
| nhis_acquisition_loss | normal_baseline | 5 | 0 | 0/0 | 0 | 0 | 0/0 | 0/0 | 0 | 0/0 | 0 | 0/0 |
| nhis_acquisition_loss | stress | 30 | 0 | 105/105 | 0 | 5 | 0/0 | 0/0 | 0 | 0/0 | 5 | -30/-30 |
| insurance_4 | normal_baseline | 5 | 5 | 0/0 | 25 | 0 | 0/0 | 0/0 | 0 | 0/0 | 0 | 0/0 |
| insurance_4 | stress | 30 | 30 | 0/0 | 150 | 0 | 0/0 | 0/0 | 0 | 0/0 | 0 | 0/0 |

## Field opportunity-change decomposition

Normalized counts below use completed shared-field pairs in baseline/stress only. Newly called errors arise when A was classification-gated and B invokes the extractor but emits a wrong/missing field. Hidden A errors arise when an A-called wrong field becomes classification-gated in B. These opportunity changes explain why introduced OCR field losses alone do not equal the signed error delta. Newly called correct fields and shared errors are shown separately; none of the unextracted outcomes becomes a field error.

Identity: B field errors − A field errors = OCR field losses + newly called field errors − field recoveries − hidden A field errors. It reconciles these completed shared-field pairs; execution/unpaired exclusions are retained in the numeric summary.

| Type | Group | A errors | B errors | OCR field losses | Newly called wrong | Newly called correct | Field recoveries | A errors hidden by B gating | Shared errors | Both unextracted | B−A errors | Reconstructed delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resident_abstract | normal_baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| resident_abstract | stress | 40 | 64 | 0 | 24 | 25 | 0 | 0 | 40 | 35 | 24 | 24 |
| nhis_payment | normal_baseline | 0 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 |
| nhis_payment | stress | 60 | 208 | 38 | 120 | 10 | 10 | 0 | 50 | 65 | 148 | 148 |
| nhis_qualification | normal_baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| nhis_qualification | stress | 54 | 85 | 0 | 36 | 6 | 5 | 0 | 49 | 35 | 31 | 31 |
| nhis_acquisition_loss | normal_baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| nhis_acquisition_loss | stress | 105 | 75 | 0 | 0 | 0 | 0 | 30 | 75 | 0 | -30 | -30 |
| insurance_4 | normal_baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 25 | 0 | 0 |
| insurance_4 | stress | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 150 | 0 | 0 |

## Complete type × condition comparison

| Type | Condition | Group | n | A type | B type | A raw / norm exact | B raw / norm exact | A raw/norm CER | B raw/norm CER | A/B unextracted | A/B false reject | A/B false pass | A/B s/page |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resident_abstract | original | normal_baseline | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1459/1.0837 |
| resident_abstract | monochrome | stress | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1379/1.0056 |
| resident_abstract | rotate_plus5 | stress | 5 | 0/5 | 5/5 | 0/0 (N/A) / 0/0 (N/A) | 20/35 (57.14%) / 20/35 (57.14%) | N/A/N/A | 0.4516/0.4138 | 35/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1942/1.0663 |
| resident_abstract | rotate_minus5 | stress | 5 | 5/5 | 5/5 | 10/35 (28.57%) / 10/35 (28.57%) | 10/35 (28.57%) / 10/35 (28.57%) | 0.7742/0.7586 | 0.7742/0.7586 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1849/1.0594 |
| resident_abstract | rotate90 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 35/35 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1857/1.0035 |
| resident_abstract | low_resolution | quality_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 25/35 (71.43%) / 25/35 (71.43%) | 0.0000/0.0000 | 0.3871/0.3448 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0110/0.5367 |
| resident_abstract | phone | stress | 5 | 3/5 | 5/5 | 6/21 (28.57%) / 6/21 (28.57%) | 11/35 (31.43%) / 11/35 (31.43%) | 0.7742/0.7586 | 0.7419/0.7241 | 14/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.4049/1.2435 |
| resident_abstract | layout_variant | stress | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1415/0.9965 |
| resident_abstract | issued_too_early | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1398/1.0073 |
| resident_abstract | issued_after_application | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1392/0.9966 |
| resident_abstract | identity_mismatch | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1464/1.0052 |
| resident_abstract | pages_incomplete | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1464/1.0125 |
| resident_abstract | wrong_document_type | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1397/1.0057 |
| resident_abstract | missing_address_dates | content_defect | 5 | 5/5 | 5/5 | 25/35 (71.43%) / 25/35 (71.43%) | 25/35 (71.43%) / 25/35 (71.43%) | 0.3871/0.3448 | 0.3871/0.3448 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1388/0.9694 |
| resident_abstract | defect_low_resolution | quality_defect | 5 | 5/5 | 0/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/35 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0061/0.4610 |
| resident_abstract | low_image_quality | quality_defect | 5 | 5/5 | 0/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/35 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1760/0.4925 |
| resident_abstract | unreadable_file | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 35/35 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | N/A/N/A |
| nhis_payment | original | normal_baseline | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1667/2.1861 |
| nhis_payment | monochrome | stress | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1622/2.1731 |
| nhis_payment | rotate_plus5 | stress | 5 | 0/5 | 5/5 | 0/0 (N/A) / 0/0 (N/A) | 5/65 (7.69%) / 5/65 (7.69%) | N/A/N/A | 0.4632/0.4954 | 65/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2520/2.2959 |
| nhis_payment | rotate_minus5 | stress | 5 | 5/5 | 5/5 | 5/65 (7.69%) / 5/65 (7.69%) | 15/65 (23.08%) / 15/65 (23.08%) | 0.9715/0.9671 | 0.4843/0.5099 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2729/2.2702 |
| nhis_payment | rotate90 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 65/65 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2078/2.0145 |
| nhis_payment | low_resolution | quality_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0203/1.6752 |
| nhis_payment | phone | stress | 5 | 0/5 | 5/5 | 0/0 (N/A) / 0/0 (N/A) | 5/65 (7.69%) / 5/65 (7.69%) | N/A/N/A | 0.4889/0.5224 | 65/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.4877/2.5022 |
| nhis_payment | layout_variant | stress | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 47/65 (72.31%) / 47/65 (72.31%) | 0.0000/0.0000 | 0.6268/0.6000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1652/2.1420 |
| nhis_payment | issued_too_early | content_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1647/2.1320 |
| nhis_payment | issued_after_application | content_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1652/2.1421 |
| nhis_payment | identity_mismatch | content_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1638/2.1636 |
| nhis_payment | pages_incomplete | content_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 5/5 (100.00%) / 0/5 (0.00%) | 0.1681/2.1590 |
| nhis_payment | wrong_document_type | content_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.0000/0.0000 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1700/2.2193 |
| nhis_payment | missing_billing_months | content_defect | 5 | 5/5 | 5/5 | 45/65 (69.23%) / 45/65 (69.23%) | 45/65 (69.23%) / 45/65 (69.23%) | 0.7692/0.7368 | 0.7692/0.7368 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1662/2.1260 |
| nhis_payment | defect_low_resolution | quality_defect | 5 | 5/5 | 5/5 | 65/65 (100.00%) / 65/65 (100.00%) | 15/65 (23.08%) / 15/65 (23.08%) | 0.0000/0.0000 | 0.9316/0.9211 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0138/1.6093 |
| nhis_payment | low_image_quality | quality_defect | 5 | 5/5 | 0/5 | 65/65 (100.00%) / 65/65 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/65 | 0/0 (N/A) / 0/0 (N/A) | 5/5 (100.00%) / 0/5 (0.00%) | 0.2307/0.5301 |
| nhis_payment | unreadable_file | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 65/65 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | N/A/N/A |
| nhis_qualification | original | normal_baseline | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1477/1.0978 |
| nhis_qualification | monochrome | stress | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1431/1.0921 |
| nhis_qualification | rotate_plus5 | stress | 5 | 0/5 | 5/5 | 0/0 (N/A) / 0/0 (N/A) | 5/35 (14.29%) / 5/35 (14.29%) | N/A/N/A | 0.9010/0.8936 | 35/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2141/1.1636 |
| nhis_qualification | rotate_minus5 | stress | 5 | 5/5 | 5/5 | 5/35 (14.29%) / 5/35 (14.29%) | 10/35 (28.57%) / 10/35 (28.57%) | 0.9010/0.8936 | 0.8020/0.7872 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2159/1.1489 |
| nhis_qualification | rotate90 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 35/35 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1832/1.1342 |
| nhis_qualification | low_resolution | quality_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 10/35 (28.57%) / 10/35 (28.57%) | 0.0000/0.0000 | 0.8020/0.7872 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0134/0.6636 |
| nhis_qualification | phone | stress | 5 | 4/5 | 5/5 | 4/28 (14.29%) / 4/28 (14.29%) | 5/35 (14.29%) / 5/35 (14.29%) | 0.9010/0.8936 | 0.9010/0.8936 | 7/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.4458/1.3517 |
| nhis_qualification | layout_variant | stress | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1467/1.0757 |
| nhis_qualification | issued_too_early | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1517/1.1307 |
| nhis_qualification | issued_after_application | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1488/1.0937 |
| nhis_qualification | identity_mismatch | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1475/1.0980 |
| nhis_qualification | pages_incomplete | content_defect | 5 | 5/5 | 5/5 | 20/35 (57.14%) / 20/35 (57.14%) | 20/35 (57.14%) / 20/35 (57.14%) | 0.6634/0.6383 | 0.6634/0.6383 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1479/1.1025 |
| nhis_qualification | wrong_document_type | content_defect | 5 | 5/5 | 5/5 | 35/35 (100.00%) / 35/35 (100.00%) | 35/35 (100.00%) / 35/35 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1473/1.1331 |
| nhis_qualification | defect_low_resolution | quality_defect | 5 | 5/5 | 0/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/35 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0084/0.5755 |
| nhis_qualification | low_image_quality | quality_defect | 5 | 5/5 | 0/5 | 35/35 (100.00%) / 35/35 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/35 | 0/0 (N/A) / 0/0 (N/A) | 5/5 (100.00%) / 0/5 (0.00%) | 0.2174/0.5150 |
| nhis_qualification | unreadable_file | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 35/35 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | N/A/N/A |
| nhis_acquisition_loss | original | normal_baseline | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1411/1.0058 |
| nhis_acquisition_loss | monochrome | stress | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1400/0.9985 |
| nhis_acquisition_loss | rotate_plus5 | stress | 5 | 5/5 | 5/5 | 5/30 (16.67%) / 5/30 (16.67%) | 5/30 (16.67%) / 5/30 (16.67%) | 0.7045/0.7143 | 0.7045/0.7143 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2010/1.0928 |
| nhis_acquisition_loss | rotate_minus5 | stress | 5 | 5/5 | 5/5 | 5/30 (16.67%) / 5/30 (16.67%) | 5/30 (16.67%) / 5/30 (16.67%) | 0.7045/0.7143 | 0.7045/0.7143 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2028/1.0619 |
| nhis_acquisition_loss | rotate90 | stress | 5 | 5/5 | 0/5 | 0/30 (0.00%) / 0/30 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.9318/0.9524 | N/A/N/A | 0/30 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1759/1.0178 |
| nhis_acquisition_loss | low_resolution | quality_defect | 5 | 5/5 | 0/5 | 30/30 (100.00%) / 30/30 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/30 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0124/0.5604 |
| nhis_acquisition_loss | phone | stress | 5 | 5/5 | 5/5 | 5/30 (16.67%) / 5/30 (16.67%) | 5/30 (16.67%) / 5/30 (16.67%) | 0.7045/0.7143 | 0.7045/0.7143 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.4322/1.2689 |
| nhis_acquisition_loss | layout_variant | stress | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1412/0.9912 |
| nhis_acquisition_loss | issued_too_early | content_defect | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1430/0.9980 |
| nhis_acquisition_loss | issued_after_application | content_defect | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1433/0.9969 |
| nhis_acquisition_loss | identity_mismatch | content_defect | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1433/1.0029 |
| nhis_acquisition_loss | pages_incomplete | content_defect | 5 | 5/5 | 5/5 | 25/30 (83.33%) / 25/30 (83.33%) | 25/30 (83.33%) / 25/30 (83.33%) | 0.1136/0.0952 | 0.1136/0.0952 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1419/1.0001 |
| nhis_acquisition_loss | wrong_document_type | content_defect | 5 | 5/5 | 5/5 | 30/30 (100.00%) / 30/30 (100.00%) | 30/30 (100.00%) / 30/30 (100.00%) | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1415/0.9909 |
| nhis_acquisition_loss | defect_low_resolution | quality_defect | 5 | 5/5 | 0/5 | 30/30 (100.00%) / 30/30 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/30 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0075/0.5027 |
| nhis_acquisition_loss | low_image_quality | quality_defect | 5 | 5/5 | 0/5 | 30/30 (100.00%) / 30/30 (100.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.0000/0.0000 | N/A/N/A | 0/30 | 0/0 (N/A) / 0/0 (N/A) | 5/5 (100.00%) / 0/5 (0.00%) | 0.2050/0.5040 |
| nhis_acquisition_loss | unreadable_file | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 30/30 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | N/A/N/A |
| insurance_4 | original | normal_baseline | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1485/1.4254 |
| insurance_4 | monochrome | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1461/1.4275 |
| insurance_4 | rotate_plus5 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2434/1.5101 |
| insurance_4 | rotate_minus5 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.2323/1.4986 |
| insurance_4 | rotate90 | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1792/1.4326 |
| insurance_4 | low_resolution | quality_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0125/0.9250 |
| insurance_4 | phone | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.4606/1.6861 |
| insurance_4 | layout_variant | stress | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/5 (0.00%) / 0/5 (0.00%) | 0/0 (N/A) / 0/0 (N/A) | 0.1535/1.4123 |
| insurance_4 | issued_too_early | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1476/1.4087 |
| insurance_4 | issued_after_application | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1475/1.4210 |
| insurance_4 | identity_mismatch | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1478/1.4098 |
| insurance_4 | pages_incomplete | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1478/1.4219 |
| insurance_4 | wrong_document_type | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.1476/1.4496 |
| insurance_4 | defect_low_resolution | quality_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.0071/0.7774 |
| insurance_4 | low_image_quality | quality_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | 0.2317/0.5477 |
| insurance_4 | unreadable_file | content_defect | 5 | 0/5 | 0/5 | 0/0 (N/A) / 0/0 (N/A) | 0/0 (N/A) / 0/0 (N/A) | N/A/N/A | N/A/N/A | 25/25 | 0/0 (N/A) / 0/0 (N/A) | 0/5 (0.00%) / 0/5 (0.00%) | N/A/N/A |

## Complete field × type × condition metrics

| Type | Condition | Field | A raw | A norm | B raw | B norm | A raw/norm CER | B raw/norm CER | A/B unextracted | A/B missing after call |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| resident_abstract | original | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | original | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | monochrome | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | rotate_plus5 | address_history_count | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| resident_abstract | rotate_plus5 | applicant_birth_date | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| resident_abstract | rotate_plus5 | applicant_name | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| resident_abstract | rotate_plus5 | birth_date | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| resident_abstract | rotate_plus5 | current_address | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| resident_abstract | rotate_plus5 | issue_date | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| resident_abstract | rotate_plus5 | name | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/0 |
| resident_abstract | rotate_minus5 | address_history_count | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | rotate_minus5 | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | rotate_minus5 | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | rotate_minus5 | birth_date | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | rotate_minus5 | current_address | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | rotate_minus5 | issue_date | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | rotate_minus5 | name | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 0/0 |
| resident_abstract | rotate90 | address_history_count | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | applicant_birth_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | applicant_name | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | birth_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | current_address | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | issue_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | rotate90 | name | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | low_resolution | address_history_count | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| resident_abstract | low_resolution | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | low_resolution | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | low_resolution | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | low_resolution | current_address | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| resident_abstract | low_resolution | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | low_resolution | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | phone | address_history_count | 0/3 | 0/3 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 2/0 | 3/5 |
| resident_abstract | phone | applicant_birth_date | 3/3 | 3/3 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 2/0 | 0/0 |
| resident_abstract | phone | applicant_name | 3/3 | 3/3 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 2/0 | 0/0 |
| resident_abstract | phone | birth_date | 0/3 | 0/3 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 2/0 | 3/5 |
| resident_abstract | phone | current_address | 0/3 | 0/3 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 2/0 | 3/5 |
| resident_abstract | phone | issue_date | 0/3 | 0/3 | 1/5 | 1/5 | 1.0000/1.0000 | 0.8000/0.8000 | 2/0 | 3/4 |
| resident_abstract | phone | name | 0/3 | 0/3 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 2/0 | 0/0 |
| resident_abstract | layout_variant | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | layout_variant | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_too_early | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | issued_after_application | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | identity_mismatch | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | pages_incomplete | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | address_history_count | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | current_address | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | wrong_document_type | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | missing_address_dates | address_history_count | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | missing_address_dates | applicant_birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | missing_address_dates | applicant_name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | missing_address_dates | birth_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | missing_address_dates | current_address | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| resident_abstract | missing_address_dates | issue_date | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | missing_address_dates | name | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| resident_abstract | defect_low_resolution | address_history_count | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | applicant_birth_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | applicant_name | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | birth_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | current_address | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | issue_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | defect_low_resolution | name | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | address_history_count | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | applicant_birth_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | applicant_name | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | birth_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | current_address | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | issue_date | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | low_image_quality | name | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| resident_abstract | unreadable_file | address_history_count | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | applicant_birth_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | applicant_name | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | birth_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | current_address | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | issue_date | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| resident_abstract | unreadable_file | name | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | original | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | original | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | original | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | original | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | original | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | original | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | monochrome | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | monochrome | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | monochrome | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | monochrome | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | monochrome | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | rotate_plus5 | 건강보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 납부자번호 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 납부총액 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 문서확인번호 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 발급일 | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| nhis_payment | rotate_plus5 | 사업장명칭 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 생년월일 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.7600/0.7600 | 5/0 | 0/2 |
| nhis_payment | rotate_plus5 | 성명 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 용도구분 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_plus5 | 월별고지금액 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.3333/0.3486 | 5/0 | 0/0 |
| nhis_payment | rotate_plus5 | 월별장기요양보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.3411/0.3679 | 5/0 | 0/0 |
| nhis_payment | rotate_plus5 | 장기요양보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.2500/0.2500 | 5/0 | 0/0 |
| nhis_payment | rotate_plus5 | 조회기간 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | rotate_minus5 | 건강보험료 | 0/5 | 0/5 | 5/5 | 5/5 | 1.0000/1.0000 | 0.0000/0.0000 | 0/0 | 5/0 |
| nhis_payment | rotate_minus5 | 납부자번호 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 납부총액 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 문서확인번호 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | rotate_minus5 | 사업장명칭 | 0/5 | 0/5 | 0/5 | 0/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 생년월일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 성명 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 용도구분 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate_minus5 | 월별고지금액 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 0.3939/0.4128 | 0/0 | 5/0 |
| nhis_payment | rotate_minus5 | 월별장기요양보험료 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 0.3643/0.3774 | 0/0 | 5/0 |
| nhis_payment | rotate_minus5 | 장기요양보험료 | 0/5 | 0/5 | 5/5 | 5/5 | 1.0000/1.0000 | 0.0000/0.0000 | 0/0 | 5/0 |
| nhis_payment | rotate_minus5 | 조회기간 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | rotate90 | 건강보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 납부자번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 납부총액 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 문서확인번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 사업장명칭 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 용도구분 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 월별고지금액 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 월별장기요양보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 장기요양보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | rotate90 | 조회기간 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | low_resolution | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | low_resolution | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | low_resolution | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | low_resolution | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | low_resolution | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | low_resolution | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | phone | 건강보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.8800/0.8800 | 5/0 | 0/0 |
| nhis_payment | phone | 납부자번호 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | phone | 납부총액 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | phone | 문서확인번호 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | phone | 발급일 | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| nhis_payment | phone | 사업장명칭 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/5 |
| nhis_payment | phone | 생년월일 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.7600/0.7600 | 5/0 | 0/2 |
| nhis_payment | phone | 성명 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/4 |
| nhis_payment | phone | 용도구분 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | phone | 월별고지금액 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.3727/0.3982 | 5/0 | 0/0 |
| nhis_payment | phone | 월별장기요양보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.3612/0.3830 | 5/0 | 0/0 |
| nhis_payment | phone | 장기요양보험료 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 0.7000/0.7000 | 5/0 | 0/1 |
| nhis_payment | phone | 조회기간 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_payment | layout_variant | 건강보험료 | 5/5 | 5/5 | 1/5 | 1/5 | 0.0000/0.0000 | 0.8000/0.8000 | 0/0 | 0/4 |
| nhis_payment | layout_variant | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | layout_variant | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 0.8152/0.8147 | 0/0 | 0/4 |
| nhis_payment | layout_variant | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 0.8155/0.8151 | 0/0 | 0/4 |
| nhis_payment | layout_variant | 장기요양보험료 | 5/5 | 5/5 | 1/5 | 1/5 | 0.0000/0.0000 | 0.8000/0.8000 | 0/0 | 0/4 |
| nhis_payment | layout_variant | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_too_early | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_too_early | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_too_early | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_too_early | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_too_early | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_after_application | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | issued_after_application | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_after_application | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_after_application | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | issued_after_application | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | identity_mismatch | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | identity_mismatch | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | identity_mismatch | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | identity_mismatch | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | identity_mismatch | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | pages_incomplete | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | pages_incomplete | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | pages_incomplete | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | pages_incomplete | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | pages_incomplete | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | wrong_document_type | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | wrong_document_type | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | wrong_document_type | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | wrong_document_type | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | wrong_document_type | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 건강보험료 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | missing_billing_months | 납부자번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 납부총액 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 문서확인번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 사업장명칭 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 용도구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | missing_billing_months | 월별고지금액 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | missing_billing_months | 월별장기요양보험료 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | missing_billing_months | 장기요양보험료 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_payment | missing_billing_months | 조회기간 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | defect_low_resolution | 건강보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 납부자번호 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 납부총액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 문서확인번호 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | defect_low_resolution | 사업장명칭 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | defect_low_resolution | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_payment | defect_low_resolution | 용도구분 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 월별고지금액 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 월별장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 장기요양보험료 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | defect_low_resolution | 조회기간 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_payment | low_image_quality | 건강보험료 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 납부자번호 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 납부총액 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 문서확인번호 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 사업장명칭 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 용도구분 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 월별고지금액 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 월별장기요양보험료 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 장기요양보험료 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | low_image_quality | 조회기간 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_payment | unreadable_file | 건강보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 납부자번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 납부총액 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 문서확인번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 사업장명칭 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 용도구분 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 월별고지금액 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 월별장기요양보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 장기요양보험료 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_payment | unreadable_file | 조회기간 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | original | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | original | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | monochrome | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | rotate_plus5 | 가구원목록 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_plus5 | 가구원수 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_plus5 | 발급일 | 0/0 | 0/0 | 5/5 | 5/5 | N/A/N/A | 0.0000/0.0000 | 5/0 | 0/0 |
| nhis_qualification | rotate_plus5 | 사업장관리번호 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_plus5 | 생년월일 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_plus5 | 성명 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_plus5 | 자격확인요청일 | 0/0 | 0/0 | 0/5 | 0/5 | N/A/N/A | 1.0000/1.0000 | 5/0 | 0/5 |
| nhis_qualification | rotate_minus5 | 가구원목록 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | rotate_minus5 | 가구원수 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | rotate_minus5 | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | rotate_minus5 | 사업장관리번호 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | rotate_minus5 | 생년월일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | rotate_minus5 | 성명 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | rotate_minus5 | 자격확인요청일 | 0/5 | 0/5 | 5/5 | 5/5 | 1.0000/1.0000 | 0.0000/0.0000 | 0/0 | 5/0 |
| nhis_qualification | rotate90 | 가구원목록 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 가구원수 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 사업장관리번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | rotate90 | 자격확인요청일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | low_resolution | 가구원목록 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_qualification | low_resolution | 가구원수 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_qualification | low_resolution | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | low_resolution | 사업장관리번호 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_qualification | low_resolution | 생년월일 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_qualification | low_resolution | 성명 | 5/5 | 5/5 | 0/5 | 0/5 | 0.0000/0.0000 | 1.0000/1.0000 | 0/0 | 0/5 |
| nhis_qualification | low_resolution | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | phone | 가구원목록 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | phone | 가구원수 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | phone | 발급일 | 4/4 | 4/4 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 1/0 | 0/0 |
| nhis_qualification | phone | 사업장관리번호 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | phone | 생년월일 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | phone | 성명 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | phone | 자격확인요청일 | 0/4 | 0/4 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 1/0 | 4/5 |
| nhis_qualification | layout_variant | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | layout_variant | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_too_early | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | issued_after_application | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | identity_mismatch | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | pages_incomplete | 가구원목록 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | pages_incomplete | 가구원수 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | pages_incomplete | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | pages_incomplete | 사업장관리번호 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_qualification | pages_incomplete | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | pages_incomplete | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | pages_incomplete | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 가구원목록 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 가구원수 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 사업장관리번호 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | wrong_document_type | 자격확인요청일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_qualification | defect_low_resolution | 가구원목록 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 가구원수 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 사업장관리번호 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | defect_low_resolution | 자격확인요청일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 가구원목록 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 가구원수 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 사업장관리번호 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | low_image_quality | 자격확인요청일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_qualification | unreadable_file | 가구원목록 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 가구원수 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 사업장관리번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_qualification | unreadable_file | 자격확인요청일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | original | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | original | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | original | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | original | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | original | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | original | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | monochrome | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | rotate_plus5 | 가입구분 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_plus5 | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | rotate_plus5 | 변동내역 | 0/5 | 0/5 | 0/5 | 0/5 | 0.6250/0.6667 | 0.6250/0.6667 | 0/0 | 0/0 |
| nhis_acquisition_loss | rotate_plus5 | 생년월일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_plus5 | 성명 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_plus5 | 취득일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_minus5 | 가입구분 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_minus5 | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | rotate_minus5 | 변동내역 | 0/5 | 0/5 | 0/5 | 0/5 | 0.6250/0.6667 | 0.6250/0.6667 | 0/0 | 0/0 |
| nhis_acquisition_loss | rotate_minus5 | 생년월일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_minus5 | 성명 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate_minus5 | 취득일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | rotate90 | 가입구분 | 0/5 | 0/5 | 0/0 | 0/0 | 1.0000/1.0000 | N/A/N/A | 0/5 | 5/0 |
| nhis_acquisition_loss | rotate90 | 발급일 | 0/5 | 0/5 | 0/0 | 0/0 | 1.0000/1.0000 | N/A/N/A | 0/5 | 5/0 |
| nhis_acquisition_loss | rotate90 | 변동내역 | 0/5 | 0/5 | 0/0 | 0/0 | 0.6250/0.6667 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | rotate90 | 생년월일 | 0/5 | 0/5 | 0/0 | 0/0 | 1.0000/1.0000 | N/A/N/A | 0/5 | 5/0 |
| nhis_acquisition_loss | rotate90 | 성명 | 0/5 | 0/5 | 0/0 | 0/0 | 1.0000/1.0000 | N/A/N/A | 0/5 | 5/0 |
| nhis_acquisition_loss | rotate90 | 취득일 | 0/5 | 0/5 | 0/0 | 0/0 | 1.0000/1.0000 | N/A/N/A | 0/5 | 5/0 |
| nhis_acquisition_loss | low_resolution | 가입구분 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_resolution | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_resolution | 변동내역 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_resolution | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_resolution | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_resolution | 취득일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | phone | 가입구분 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | phone | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | phone | 변동내역 | 0/5 | 0/5 | 0/5 | 0/5 | 0.6250/0.6667 | 0.6250/0.6667 | 0/0 | 0/0 |
| nhis_acquisition_loss | phone | 생년월일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | phone | 성명 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | phone | 취득일 | 0/5 | 0/5 | 0/5 | 0/5 | 1.0000/1.0000 | 1.0000/1.0000 | 0/0 | 5/5 |
| nhis_acquisition_loss | layout_variant | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | layout_variant | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | layout_variant | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | layout_variant | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | layout_variant | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | layout_variant | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_too_early | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | issued_after_application | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | identity_mismatch | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 변동내역 | 0/5 | 0/5 | 0/5 | 0/5 | 0.6250/0.6667 | 0.6250/0.6667 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | pages_incomplete | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 가입구분 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 발급일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 변동내역 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 생년월일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 성명 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | wrong_document_type | 취득일 | 5/5 | 5/5 | 5/5 | 5/5 | 0.0000/0.0000 | 0.0000/0.0000 | 0/0 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 가입구분 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 변동내역 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | defect_low_resolution | 취득일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 가입구분 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 발급일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 변동내역 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 생년월일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 성명 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | low_image_quality | 취득일 | 5/5 | 5/5 | 0/0 | 0/0 | 0.0000/0.0000 | N/A/N/A | 0/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 가입구분 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 변동내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| nhis_acquisition_loss | unreadable_file | 취득일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | original | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | original | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | original | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | original | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | original | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | monochrome | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | monochrome | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | monochrome | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | monochrome | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | monochrome | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_plus5 | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_plus5 | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_plus5 | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_plus5 | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_plus5 | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_minus5 | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_minus5 | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_minus5 | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_minus5 | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate_minus5 | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate90 | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate90 | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate90 | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate90 | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | rotate90 | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_resolution | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_resolution | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_resolution | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_resolution | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_resolution | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | phone | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | phone | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | phone | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | phone | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | phone | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | layout_variant | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | layout_variant | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | layout_variant | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | layout_variant | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | layout_variant | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_too_early | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_too_early | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_too_early | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_too_early | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_too_early | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_after_application | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_after_application | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_after_application | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_after_application | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | issued_after_application | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | identity_mismatch | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | identity_mismatch | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | identity_mismatch | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | identity_mismatch | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | identity_mismatch | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | pages_incomplete | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | pages_incomplete | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | pages_incomplete | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | pages_incomplete | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | pages_incomplete | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | wrong_document_type | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | wrong_document_type | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | wrong_document_type | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | wrong_document_type | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | wrong_document_type | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | defect_low_resolution | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | defect_low_resolution | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | defect_low_resolution | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | defect_low_resolution | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | defect_low_resolution | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_image_quality | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_image_quality | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_image_quality | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_image_quality | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | low_image_quality | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | unreadable_file | 가입내역 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | unreadable_file | 발급번호 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | unreadable_file | 발급일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | unreadable_file | 생년월일 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |
| insurance_4 | unreadable_file | 성명 | 0/0 | 0/0 | 0/0 | 0/0 | N/A/N/A | N/A/N/A | 5/5 | 0/0 |

## Reupload codes by group

All ten requested codes are shown, including zeros. A document can contribute to more than one code count.

| Group | Code | A wrong FAIL | B wrong FAIL | A all confirmed | B all confirmed |
| --- | --- | --- | --- | --- | --- |
| normal_baseline | DOCUMENT_ISSUED_AFTER_APPLICATION | 0 | 0 | 0 | 0 |
| normal_baseline | DOCUMENT_ISSUED_TOO_EARLY | 0 | 0 | 0 | 0 |
| normal_baseline | IDENTITY_MISMATCH | 0 | 0 | 0 | 0 |
| normal_baseline | IMAGE_RESOLUTION_TOO_LOW | 0 | 0 | 0 | 0 |
| normal_baseline | LOW_IMAGE_QUALITY | 0 | 0 | 0 | 0 |
| normal_baseline | MISSING_ADDRESS_DATES | 0 | 0 | 0 | 0 |
| normal_baseline | MISSING_BILLING_MONTHS | 0 | 0 | 0 | 0 |
| normal_baseline | PAGES_INCOMPLETE | 0 | 0 | 0 | 0 |
| normal_baseline | UNREADABLE_FILE | 0 | 0 | 0 | 0 |
| normal_baseline | WRONG_DOCUMENT_TYPE | 0 | 0 | 0 | 0 |
| stress | DOCUMENT_ISSUED_AFTER_APPLICATION | 0 | 0 | 0 | 0 |
| stress | DOCUMENT_ISSUED_TOO_EARLY | 0 | 0 | 0 | 0 |
| stress | IDENTITY_MISMATCH | 0 | 0 | 0 | 0 |
| stress | IMAGE_RESOLUTION_TOO_LOW | 0 | 0 | 0 | 0 |
| stress | LOW_IMAGE_QUALITY | 0 | 0 | 0 | 0 |
| stress | MISSING_ADDRESS_DATES | 0 | 0 | 0 | 0 |
| stress | MISSING_BILLING_MONTHS | 0 | 0 | 0 | 0 |
| stress | PAGES_INCOMPLETE | 0 | 0 | 0 | 0 |
| stress | UNREADABLE_FILE | 0 | 0 | 0 | 0 |
| stress | WRONG_DOCUMENT_TYPE | 0 | 0 | 0 | 0 |
| quality_defect | DOCUMENT_ISSUED_AFTER_APPLICATION | 0 | 0 | 0 | 0 |
| quality_defect | DOCUMENT_ISSUED_TOO_EARLY | 0 | 0 | 0 | 0 |
| quality_defect | IDENTITY_MISMATCH | 0 | 0 | 0 | 0 |
| quality_defect | IMAGE_RESOLUTION_TOO_LOW | 0 | 0 | 5 | 20 |
| quality_defect | LOW_IMAGE_QUALITY | 0 | 0 | 45 | 30 |
| quality_defect | MISSING_ADDRESS_DATES | 0 | 0 | 0 | 0 |
| quality_defect | MISSING_BILLING_MONTHS | 0 | 0 | 0 | 0 |
| quality_defect | PAGES_INCOMPLETE | 0 | 0 | 0 | 0 |
| quality_defect | UNREADABLE_FILE | 0 | 0 | 0 | 0 |
| quality_defect | WRONG_DOCUMENT_TYPE | 0 | 0 | 0 | 0 |
| content_defect | DOCUMENT_ISSUED_AFTER_APPLICATION | 0 | 0 | 15 | 10 |
| content_defect | DOCUMENT_ISSUED_TOO_EARLY | 0 | 0 | 20 | 15 |
| content_defect | IDENTITY_MISMATCH | 0 | 0 | 5 | 5 |
| content_defect | IMAGE_RESOLUTION_TOO_LOW | 0 | 0 | 0 | 0 |
| content_defect | LOW_IMAGE_QUALITY | 0 | 0 | 0 | 0 |
| content_defect | MISSING_ADDRESS_DATES | 0 | 0 | 0 | 0 |
| content_defect | MISSING_BILLING_MONTHS | 0 | 0 | 0 | 0 |
| content_defect | PAGES_INCOMPLETE | 0 | 0 | 0 | 5 |
| content_defect | UNREADABLE_FILE | 0 | 0 | 25 | 25 |
| content_defect | WRONG_DOCUMENT_TYPE | 0 | 0 | 20 | 20 |

## Weakest diagnostic groups

Rankings exclude deliberately defective cases and keep baseline and stress document views separate. They keep conditional field accuracy, field coverage and independent type accuracy separate. An uncalled extractor is ranked by classification/coverage, not assigned 0% conditional field accuracy.

### Document types (baseline and stress kept separate)

| Group | n | B type accuracy | B conditional raw/norm exact | B correct coverage | B unextracted |
| --- | --- | --- | --- | --- | --- |
| insurance_4 / normal_baseline | 5 | 0.00% | 0/0 (N/A) / 0/0 (N/A) | 0.00% | 25 |
| insurance_4 / stress | 30 | 0.00% | 0/0 (N/A) / 0/0 (N/A) | 0.00% | 150 |
| nhis_payment / stress | 30 | 83.33% | 117/325 (36.00%) / 117/325 (36.00%) | 30.00% | 65 |
| nhis_acquisition_loss / stress | 30 | 83.33% | 75/150 (50.00%) / 75/150 (50.00%) | 41.67% | 30 |
| nhis_qualification / stress | 30 | 83.33% | 90/175 (51.43%) / 90/175 (51.43%) | 42.86% | 35 |
| resident_abstract / stress | 30 | 83.33% | 111/175 (63.43%) / 111/175 (63.43%) | 52.86% | 35 |
| nhis_payment / normal_baseline | 5 | 100.00% | 45/65 (69.23%) / 45/65 (69.23%) | 69.23% | 0 |
| nhis_acquisition_loss / normal_baseline | 5 | 100.00% | 30/30 (100.00%) / 30/30 (100.00%) | 100.00% | 0 |

### Expected-valid conditions only

| Group | n | B type accuracy | B conditional raw/norm exact | B correct coverage | B unextracted |
| --- | --- | --- | --- | --- | --- |
| rotate90 | 25 | 0.00% | 0/0 (N/A) / 0/0 (N/A) | 0.00% | 190 |
| phone | 25 | 80.00% | 26/165 (15.76%) / 26/165 (15.76%) | 13.68% | 25 |
| rotate_plus5 | 25 | 80.00% | 35/165 (21.21%) / 35/165 (21.21%) | 18.42% | 25 |
| rotate_minus5 | 25 | 80.00% | 40/165 (24.24%) / 40/165 (24.24%) | 21.05% | 25 |
| monochrome | 25 | 80.00% | 145/165 (87.88%) / 145/165 (87.88%) | 76.32% | 25 |
| original | 25 | 80.00% | 145/165 (87.88%) / 145/165 (87.88%) | 76.32% | 25 |
| layout_variant | 25 | 80.00% | 147/165 (89.09%) / 147/165 (89.09%) | 77.37% | 25 |

### Fields (called opportunities only)

| Type | Group | Field | Raw correct/called | Normalized correct/called | Normalized CER | Unextracted |
| --- | --- | --- | --- | --- | --- | --- |
| nhis_payment | normal_baseline | 건강보험료 | 0/5 | 0/5 | 1.0000 | 0 |
| nhis_payment | normal_baseline | 월별고지금액 | 0/5 | 0/5 | 1.0000 | 0 |
| nhis_payment | normal_baseline | 월별장기요양보험료 | 0/5 | 0/5 | 1.0000 | 0 |
| nhis_payment | normal_baseline | 장기요양보험료 | 0/5 | 0/5 | 1.0000 | 0 |
| nhis_payment | stress | 월별고지금액 | 0/25 | 0/25 | 0.5949 | 5 |
| nhis_payment | stress | 월별장기요양보험료 | 0/25 | 0/25 | 0.5887 | 5 |
| nhis_payment | stress | 건강보험료 | 6/25 | 6/25 | 0.7360 | 5 |
| nhis_payment | stress | 장기요양보험료 | 6/25 | 6/25 | 0.5500 | 5 |
| nhis_acquisition_loss | stress | 가입구분 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_acquisition_loss | stress | 생년월일 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_acquisition_loss | stress | 성명 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_acquisition_loss | stress | 취득일 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_payment | stress | 납부자번호 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_payment | stress | 납부총액 | 10/25 | 10/25 | 0.6000 | 5 |
| nhis_payment | stress | 문서확인번호 | 10/25 | 10/25 | 0.6000 | 5 |

## Source decisions and interpretation

Five samples are different fictitious identity/date parameter sets; they share source layout/font families. They are not five independent issuer templates and do not establish real-document population accuracy. Purpose marks and ambiguous source/table layouts are retained in baseline and stress runs. Stage A exposes those interactions without modifying operational recognition.

No improvement to OCR, classification, extraction or decision logic was implemented. Candidate work must first distinguish A-baseline failures from A-correct/B-lost fields, then inspect template/geometry/segmentation evidence. Quality FAIL on deliberately undersized originals is expected and cannot enter normal false-rejection rates. More review outcomes do not establish correct automatic detection.

### Source-change evidence

- S01: Original layouts, purpose markings and table cells are unchanged from documentai_synth.sources(), nhis_form_samples and p2_payment_samples; ambiguity is retained, not repaired to obtain PASS.
- S02: documentai_synth.sources() uses sample % 4. V2 replaces only fictitious identity/date values with five distinct parameter sets; no labels, column positions or original typography are removed.
- S03: Insurance output timestamp follows the varied issue date, preserving the +1 day relationship printed by insurance_portal_cells(); qualification request precedes issue and validity remains after it.
- S04: Legacy defects() replaces every printed 2026 year but leaves other truth dates unchanged and hardcodes issue March03. V2 changes all authored 2026 truth date values to the same negative-case year, including qualification request dates, while retaining the varied issue month/day.
- S05: layout_variant adds bounded row-position jitter as a separately labeled stress case; original geometry and all source text are retained. Existing p2 geometry/jitter tests motivate stress coverage, not a baseline correction.

## Reproducibility and source-review record

All 410 pairs completed (820 stage evaluations), with five distinct submitted inputs in each of 82 applicable document/condition cells. All 25 original source definitions are unique within type. Reference and own share each input hash. No original layout/font/label was corrected or removed. See [source-decisions.md](source-decisions.md) for S01–S07 evidence and [validation-v2.md](validation-v2.md) for full regressions. Old reports remain unchanged.

Ten qualification negative-date pairs were selectively replayed after correcting request-date truth to match the unchanged printed source. Every submitted hash matched the first run, every non-request field/verdict/classification result matched, and only the relevant request-date metric changed. The replay model was warmed before timing to match the original warm cases. Original as-run JSON/report remain preserved; reviewed results replace those ten pairs without pooling repetitions.

The old 36.84% statistic and new called-extractor accuracy use different populations and denominators. Their difference is a measurement-method change, not an engine improvement; no operational logic changed.
