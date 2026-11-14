# Paging test impact — approval requested

No existing test assertion or fixture provider has been edited. With unchanged markerless inputs, the new explicit uncertainty review changes 24 first verdict checks from PASS to NEEDS_REVIEW and 2 income outcomes from MET/OVER_LIMIT to UNDETERMINED across 26 parameter cases: 23 pre-existing main cases and 3 stage-2 cases. Engine: 2 failures / 1,582 passes / 3 skips. Backend snapshot: 24 failures / 1,329 passes (includes the first 39 new paging cases). These are intermediate expectation-impact runs, not final green gates.

| File and test (parameter case) | Before | After, same input |
| --- | --- | --- |
| `engine_v2/tests/test_p2_payment_headers.py::test_group_header_glyphs_on_four_lines_still_require_the_ordered_eight_columns` | PASS | NEEDS_REVIEW |
| `engine_v2/tests/test_p2_shape3.py::test_exact_shape_is_complete_with_required_issue_date[payment-\uac74\uac15\ubcf4\ud5d8\ub8cc\ub0a9\ubd80\ud655\uc778\uc11c]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_income_extracted_review.py::test_extracted_ab_survives_renaming_validation_storage_and_real_review[blank-blank-FAIL]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_income_extracted_review.py::test_extracted_ab_survives_renaming_validation_storage_and_real_review[present-present-PASS]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_income_extracted_review.py::test_extracted_ab_survives_renaming_validation_storage_and_real_review[present-blank-NEEDS_REVIEW]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_income_extracted_review.py::test_extracted_ab_survives_renaming_validation_storage_and_real_review[unreadable-blank-NEEDS_REVIEW]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_facts.py::test_complete_matching_payment_preserves_income_scoring[False]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_facts.py::test_complete_matching_payment_preserves_income_scoring[True]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_facts.py::test_complete_matching_payment_keeps_pipeline_pass[True]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_uploads.py::test_payment_upload_matches_identity_and_persists_all_corrections[False-False]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_uploads.py::test_payment_upload_matches_identity_and_persists_all_corrections[False-True]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_uploads.py::test_payment_upload_matches_identity_and_persists_all_corrections[True-False]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_uploads.py::test_payment_upload_matches_identity_and_persists_all_corrections[True-True]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_p2_payment_uploads.py::test_payment_text_layer_upload_keeps_same_financial_field_contract` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_failure_certainty.py::test_normal_period_and_annual_zero_placeholders_remain_pass` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_failure_certainty.py::test_uncertain_annual_zero_placeholders_do_not_change_other_requested_months` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_failure_certainty.py::test_proven_ocr_corrections_of_annual_zeros_preserve_normal_pass[False]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_failure_certainty.py::test_proven_ocr_corrections_of_annual_zeros_preserve_normal_pass[True]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_stage2_routes.py::test_repaired_shapes_traverse_actual_image_upload_without_changing_average[adjustment]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_stage2_routes.py::test_repaired_shapes_traverse_actual_image_upload_without_changing_average[clipped]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_payment_stage2_routes.py::test_repaired_shapes_traverse_actual_image_upload_without_changing_average[fused]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_review_regressions.py::test_legacy_payment_sum_failure_controls_direct_verdict_and_financial_trust[False-legacy]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_review_regressions.py::test_legacy_payment_sum_failure_controls_direct_verdict_and_financial_trust[False-month-only]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_review_regressions.py::test_legacy_payment_sum_failure_reaches_actual_text_layer_upload[False-month-only]` | PASS | NEEDS_REVIEW |
| `demo/backend/tests/test_verify_upload.py::test_income_uses_three_real_synthetic_files[normal-MET-X]` | income_status: MET | income_status: UNDETERMINED; blockers: X |
| `demo/backend/tests/test_verify_upload.py::test_income_uses_three_real_synthetic_files[excess-OVER_LIMIT-O]` | income_status: OVER_LIMIT; blockers: O | income_status: UNDETERMINED; blockers: X |

## Recommended adjustment

Preserve the existing header/table/period/income tests and their original positive/negative expectations by printing an authored 1/1 folio in those tests’ local synthetic payment inputs. This supplies actual observable evidence to the production collector, rather than injecting a policy or bypassing checks. Do not modify p2_payment_samples, p2_form_samples, documentai_synth/corpus_v2, measurement truth/metrics or the frozen benchmark inputs. Dedicated new paging tests retain absent/unreadable-marker NEEDS_REVIEW and explicit markerless-policy behavior.

Proposed test-only input edits are limited to the files in the table (plus the stage-2 local shape helper). Local helper changes may affect related parameter cases in the same modules, but keep all original amount/date/identity/period/arithmetic values and assertions. Add only the printed folio and reverify the existing checks. No old PASS is silently replaced with NEEDS_REVIEW, and no income/arithmetic assertion is removed.

The income-oriented cases stop at their first PASS-to-REVIEW assertion. Downstream changes to premium trust/score are expected if inputs stay markerless; the current run does not claim a complete new downstream expectation inventory. Completing their printed input preserves their original income purpose and avoids weakening those assertions.

Alternative: retain the markerless inputs and propose explicit review/income-expectation changes with a separate exact inventory; this is not the recommendation. User approval is required before either path. The full 410-pair corpus is unchanged and is compared independently.


## Superseding review

User did NOT approve the input edits proposed above. See `paging-refinement-review.md`: isolated table-completeness refinement restores all 26 original assertions without input changes (remaining impact 0). This historical impact inventory is retained as evidence of the strict guard, not current authorization to change tests.
