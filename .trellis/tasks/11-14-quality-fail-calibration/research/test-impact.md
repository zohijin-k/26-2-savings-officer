# Test impact and proposed expectation approval inventory

## Approved existing expectation changes after user correction

The user approved implementation and these expectation changes on 2026-11-14, correcting unknown-type low-quality cases to retain FAIL. The original five-test proposal therefore reduces to four tests. No additional approval is needed for the retained existing FAIL expectations. Verify these values against the unchanged baseline before editing. Any additional changed expectation requires a fresh report and explicit approval.

| File | Test / case | Before | Proposed after | Reason |
| --- | --- | --- | --- | --- |
| `demo/backend/tests/test_quality_failure_policy.py` | `test_quality_fail_survives_confidence_and_every_early_return`, path normal, confidence 0/.4/1 | Result FAIL, one LOW_IMAGE_QUALITY FAIL, QUALITY_REUPLOAD_GUIDANCE, no allowance to submit | Result NEEDS_REVIEW, one LOW_IMAGE_QUALITY NEEDS_REVIEW, review guidance allowing submission | This type has no failed essential-field check. Aggregate confidence alone supplies no essential-field failure evidence. |
| Same file | `test_nhis_identity_review_cannot_downgrade_measured_quality` | Result FAIL, LOW_IMAGE_QUALITY FAIL | Result NEEDS_REVIEW, LOW_IMAGE_QUALITY NEEDS_REVIEW, IDENTITY_UNCERTAIN retained | Name, birth and issue date were read. Their mismatch supplies identity uncertainty, without an essential-field unreadability finding. |
| `demo/backend/tests/test_nhis_recent_history.py` | `test_short_explicit_period_is_fail_only_when_readable`, confidence .95 and quality .4 | Result FAIL and LOW_IMAGE_QUALITY FAIL | Result NEEDS_REVIEW and LOW_IMAGE_QUALITY NEEDS_REVIEW | The explicit period and required identity/date fields were read. Its existing NHIS_HISTORY_PERIOD_MISSING NEEDS_REVIEW result remains. Other parameter cases keep their current expected grades. |
| `demo/backend/tests/run_p18_applicant_precheck_scenarios.py` | `test_uncertainty` call `quality_rejection("저화질", ...)`, helper `quality_rejection` | 상태 FAIL, 확정 화질 FAIL predicate True, PDF 재발급 안내 predicate True | 상태 NEEDS_REVIEW, LOW_IMAGE_QUALITY review predicate True, review guidance predicate True | The input is the previously complete resident form with quality changed alone. Keep the LOW_IMAGE_QUALITY presence assertion True. Replace the rejection-oriented helper name and labels to match this specific complete-form test. |

Preserve existing test function names unless a name becomes misleading after the approved change. The table's original names identify approval scope even if a rename is reviewed in the eventual diff. Preserve parameter coverage and assertion counts where practical, reporting actual count differences.

## Existing regressions whose expected grades remain

| File | Tests / cases | Required result and reason |
| --- | --- | --- |
| `demo/backend/tests/test_quality_failure_policy.py` | `test_quality_fail_survives_confidence_and_every_early_return`, daily-incomplete and nhis-incomplete, all confidences | LOW_IMAGE_QUALITY FAIL and overall FAIL because existing REQUIRED_FIELD_UNREADABLE is present. |
| `demo/backend/tests/test_quality_failure_policy.py` | `test_quality_fail_survives_confidence_and_every_early_return`, unknown path at every confidence | Overall FAIL and LOW_IMAGE_QUALITY FAIL with mandatory reupload guidance, as explicitly required by the user. |
| `demo/backend/tests/test_verify_upload.py` | `test_image_portal_title_interleaving_retains_existing_uncertainty` | Preserve document_status FAIL, UNKNOWN_DOCUMENT_TYPE NEEDS_REVIEW, LOW_IMAGE_QUALITY FAIL and blockers O. Removed from the expectation-change inventory after the user correction. |
| Same file | `test_only_quality_leaves_review_only_vocabulary` | Dynamic quality grading does not put LOW_IMAGE_QUALITY into the globally review-only vocabulary. Existing high-quality/low-confidence result remains review. |
| Same file | `test_receipt_ocr_absence_retains_quality_specific_failure_only_when_measured` | 970px unavailable OCR retains quality FAIL through receipt postprocessing, 586px retains IMAGE_RESOLUTION_TOO_LOW FAIL, and normal-size unavailable OCR retains review. |
| Same file | `test_specific_date_page_and_quality_failures_all_reach_one_blocker`; `test_actual_synthetic_image_upload_and_final_check_show_both_failures` | Both quality and independent content failures remain, including the single blocker and submit rejection. Existing applicant identity is unreadable. |
| `demo/backend/tests/test_followup_failure_acceptance.py` | `test_sparse_address_document_and_actual_blocker_agree`, all five variants; `test_sparse_address_actual_image_cli_blocks_without_value_output` | Preserve quality FAIL, blockers and independent missing-date evidence. The focused diagnostic found RESIDENT_APPLICANT_UNREADABLE in all five variants. |
| `demo/backend/tests/test_followup_address_reproduction.py` | `test_sparse_header_proves_date_omission_despite_quality_review` | Preserve FAIL, LOW_IMAGE_QUALITY presence and MISSING_ADDRESS_DATES FAIL. |
| `demo/backend/tests/test_applicant_failure_findings.py` | `test_source_shaped_case_cli_shows_only_applicant_failures`, cases 5 and 7; mixed-severity projection tests | Preserve authored failure lists and complete officer findings. Grade-aware quality policy must use resident applicant unreadability, and applicant projection remains grade-based. |
| `demo/backend/tests/test_objective_image_quality.py` | `test_raw_original_short_side_bands_are_preserved`; `test_original_embedded_pdf_dpi_bands_are_preserved`; normal/text/mixed/attachment/rotation tests | All numeric measurement expectations and code-presence assertions retain their existing meanings. |
| `demo/backend/tests/test_resolution_evidence.py` | All tests, including `test_only_narrow_original_pixel_boundary_rejects_unknown` and readable-tiny type-specific cases | Preserve the separate severe-resolution predicate and applicable field selection. |
| `demo/backend/tests/test_address_resolution_failures.py` | Missing-date/header and actual image-upload cases | Preserve independent confirmed missing-date and severe-resolution failures. |
| `demo/backend/tests/test_payment_failure_certainty.py` | Password, original date/month/amount certainty tests | Preserve actual unreadable-file FAIL and independent payment content rules. |
| `engine_v2/tests/test_documentai_staged_report.py` | `test_quality_and_content_defects_have_own_false_pass_denominators`; `test_codes_are_deduplicated_per_case_and_require_final_fail` | Preserve metric definitions and authored report-fixture expectations. |
| `engine_v2/tests/test_documentai_staged.py`, `test_documentai_corpus_v2.py`, `test_documentai_synth.py` | Paired production routing, invalid-file assessment, source taxonomy, legacy metric fixtures | Preserve corpus, denominator, code-severity and read-only measurement contracts. |

## Added regression coverage

- Grade matrix for measured quality versus essential readability, including threshold equality, multiple missing fields, early returns and repeated finalization.
- Readable required values with low overall confidence, screen-capture suspicion or identity uncertainty produce review-grade quality. A field's explicit unreadability produces quality FAIL only below the quality cutoff.
- Receipt and consent observations arriving after check_document affect the conjunction and preserve one quality finding. Good-quality unavailable OCR follows the prior review outcome.
- Every low-quality outcome remains non-PASS, including type-unknown FAIL and unsupported essential-check review paths.
- Actual synthetic upload/list/final-check/submit/officer agreement for review-grade quality alone, quality FAIL plus unreadable fields, and review-grade quality plus an independent content FAIL.
- Real submission-time engine stage1/final/payload results carry review-grade quality and retain independent failures. Legacy engine callers without assessed quality evidence retain compatible behavior.
- Applicant review message/action and officer badge/detail are checked against saved grades. The officer list keeps these documents in its existing non-PASS group.

## Final new-test inventory

`demo/backend/tests/test_quality_assessment_parity.py` contains 44 parameterized cases. The initial 24 cover shared boundaries, unreadability, unknown type, late observations, legacy evidence and actual upload/submission/officer APIs. An additional 20 cover the actual certificate checklist's accepted transcript alternative, duplicate type combinations in both orders, independent content failures, default matching guards and duplicate unknown/unreadable quality failures. These are added regression cases. Existing expectation changes remain the four functions listed above.

## Full regression scope

Run engine_v2 pytest, backend pytest, all 18 backend scenario modules sequentially and frontend lint/build. The supplied counts are comparison baselines pending actual execution. Run frontend npm test as required by the officer frontend spec. No real-document measurement is part of these runs.
