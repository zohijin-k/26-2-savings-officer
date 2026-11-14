# Final synthetic v2 comparison

The before and final after runs used samples 5 and seed 20261113, with 410 paired cases and 820 stage evaluations per run. Reference A injects the generated text-layer words through the production image path. Own B performs actual own OCR. All inputs are authored synthetic documents.

All 410 case keys, input fingerprints and source metadata match. The measurement source, original quality measurement code, dependency versions and pinned own-model hashes match. Classification, extractor invocation, field exact/CER metrics and reading counts have zero differences. All attempts completed with zero execution failures in both runs.

False rejection uses expected VALID cases with final FAIL plus a confirmed FAIL-severity reupload code. False acceptance uses PASS on an expected negative case. NEEDS_REVIEW has its own count. The comparison checked 250 group/type/condition/cell stage slices and every individual defect case. New defect PASS cases and increased false-acceptance slices are both zero.

| Population | Stage | False rejection before | After | False acceptance before | After |
| --- | --- | --- | --- | --- | --- |
| valid_combined | reference | 0/175 (0.00%) | 0/175 (0.00%) | N/A | N/A |
| valid_combined | own | 0/175 (0.00%) | 0/175 (0.00%) | N/A | N/A |
| normal_baseline | reference | 0/25 (0.00%) | 0/25 (0.00%) | N/A | N/A |
| normal_baseline | own | 0/25 (0.00%) | 0/25 (0.00%) | N/A | N/A |
| stress | reference | 0/150 (0.00%) | 0/150 (0.00%) | N/A | N/A |
| stress | own | 0/150 (0.00%) | 0/150 (0.00%) | N/A | N/A |
| quality_defect | reference | N/A | N/A | 15/75 (20.00%) | 15/75 (20.00%) |
| quality_defect | own | N/A | N/A | 0/75 (0.00%) | 0/75 (0.00%) |
| content_defect | reference | N/A | N/A | 5/160 (3.12%) | 5/160 (3.12%) |
| content_defect | own | N/A | N/A | 0/160 (0.00%) | 0/160 (0.00%) |

## Verdict distributions

| Population | Stage | Before | After |
| --- | --- | --- | --- |
| valid_combined | reference | {"NEEDS_REVIEW": 130, "PASS": 45} | {"NEEDS_REVIEW": 130, "PASS": 45} |
| valid_combined | own | {"NEEDS_REVIEW": 145, "PASS": 30} | {"NEEDS_REVIEW": 145, "PASS": 30} |
| normal_baseline | reference | {"NEEDS_REVIEW": 10, "PASS": 15} | {"NEEDS_REVIEW": 10, "PASS": 15} |
| normal_baseline | own | {"NEEDS_REVIEW": 15, "PASS": 10} | {"NEEDS_REVIEW": 15, "PASS": 10} |
| stress | reference | {"NEEDS_REVIEW": 120, "PASS": 30} | {"NEEDS_REVIEW": 120, "PASS": 30} |
| stress | own | {"NEEDS_REVIEW": 130, "PASS": 20} | {"NEEDS_REVIEW": 130, "PASS": 20} |
| quality_defect | reference | {"FAIL": 50, "NEEDS_REVIEW": 10, "PASS": 15} | {"FAIL": 10, "NEEDS_REVIEW": 50, "PASS": 15} |
| quality_defect | own | {"FAIL": 50, "NEEDS_REVIEW": 25} | {"FAIL": 45, "NEEDS_REVIEW": 30} |
| content_defect | reference | {"FAIL": 85, "NEEDS_REVIEW": 70, "PASS": 5} | {"FAIL": 85, "NEEDS_REVIEW": 70, "PASS": 5} |
| content_defect | own | {"FAIL": 80, "NEEDS_REVIEW": 80} | {"FAIL": 80, "NEEDS_REVIEW": 80} |

Paired cases 410. Input fingerprints and source metadata match.
New defect PASS cases 0. False-acceptance slice increases 0. Classification/extraction metric differences 0.

## Changed verdicts

| Case | Stage | Group | Before | After | Confirmed reupload codes before | After |
| --- | --- | --- | --- | --- | --- | --- |
| s1_resident_abstract_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_resident_abstract_low_resolution | own | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_resident_abstract_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_payment_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_payment_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_qualification_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_qualification_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_acquisition_loss_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s1_nhis_acquisition_loss_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_resident_abstract_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_resident_abstract_low_resolution | own | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_resident_abstract_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_payment_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_payment_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_qualification_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_qualification_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_acquisition_loss_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s2_nhis_acquisition_loss_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_resident_abstract_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_resident_abstract_low_resolution | own | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_resident_abstract_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_payment_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_payment_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_qualification_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_qualification_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_acquisition_loss_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s3_nhis_acquisition_loss_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_resident_abstract_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_resident_abstract_low_resolution | own | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_resident_abstract_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_payment_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_payment_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_qualification_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_qualification_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_acquisition_loss_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s4_nhis_acquisition_loss_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_resident_abstract_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_resident_abstract_low_resolution | own | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_resident_abstract_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_payment_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_payment_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_qualification_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_qualification_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_acquisition_loss_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |
| s5_nhis_acquisition_loss_defect_low_resolution | reference | quality_defect | FAIL | NEEDS_REVIEW | LOW_IMAGE_QUALITY |  |

## Interpretation

Forty reference-stage and five own-stage quality-defect cases changed from FAIL to NEEDS_REVIEW. Every changed case retains a non-PASS outcome. No source labels or metric definitions changed during comparison.

Valid-case false rejection was already zero before the change, so this corpus cannot quantify a reduction in that rate. Reference-stage quality false acceptance 15/75 and content false acceptance 5/160 existed in the unchanged baseline and remain at those levels. Own false acceptance remains zero in both defect groups.
