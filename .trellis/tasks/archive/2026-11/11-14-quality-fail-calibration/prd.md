# Calibrate low-image-quality failure conditions

## Goal

Reduce unnecessary applicant reupload requests while retaining quality FAIL for unreadable essential fields or failed document classification.

## Background

The user supplied these field-extraction rates for quality-warning versus other documents. Resident abstract 83% versus 76%, NHIS acquisition/loss 73% versus 77%, four-insurance confirmation 46% versus 47%, payment confirmation 40% versus 43%, and qualification confirmation 31% versus 46%. These supplied percentages are the only real-document measurement observations recorded here. Development evidence uses synthetic inputs.

## Requirements

| ID | Requirement |
| --- | --- |
| R1 | LOW_IMAGE_QUALITY has severity FAIL only when measured quality is below the existing threshold and either classification failed or existing essential-field checks establish unreadability. |
| R2 | Below-threshold quality with successful classification and readable essential fields produces LOW_IMAGE_QUALITY NEEDS_REVIEW. Every below-threshold document has an overall grade of at least NEEDS_REVIEW. |
| R3 | IMAGE_RESOLUTION_TOO_LOW and UNREADABLE_FILE keep their existing FAIL behavior. Independent content failures retain their own grades and submission blockers. |
| R4 | Preserve original-image measurement, the 1,000px short-edge criterion, 150dpi criterion and current quality score bands. |
| R5 | Applicant guidance follows the quality finding's grade. Review-grade guidance allows officer review without demanding reupload. Upload and submission-time rechecking use one shared quality rule and produce matching results, including unknown-type and OCR-unavailable cases. Officer document and application results agree with the upload assessment. |
| R6 | Report every proposed existing-test expectation change with file, test name, before/after values and reason, and obtain approval before editing expectations. Newly discovered changes require a fresh review. |
| R7 | Run synthetic measurement v2 before and after implementation with the same seed, sample count and source definitions. Compare false rejection and quality/content false acceptance using explicit numerators and denominators. Stop and report any increased false acceptance. |
| R8 | Before any commit, present git diff --stat main and actual engine_v2, backend, all 18 scenario and frontend lint/build results. Wait for explicit commit approval. |
| R9 | Persist research and plans on a new branch. Implementation begins only after the user approves the final plan in a subsequent message. Planning artifacts contain no real-document paths or filenames. |

## Acceptance Criteria

- A1, R1/R2. The same synthetic complete form at low quality yields review, and an essential-field-unreadable variant yields quality FAIL. Good quality plus unreadable fields follows the existing review policy. Low OCR confidence or an identity mismatch with fully read values cannot independently make the quality finding FAIL.
- A2, R2/R3. Early-return paths, unavailable OCR, receipt/consent postprocessing and submission-time rechecking preserve the review floor and confirmed file/content defects.
- A3, R4. Existing pixel/DPI boundary tests retain their numeric expectations, including the separate severe-resolution predicate.
- A4, R5. Synthetic upload, list, final-check, submission and officer APIs agree. Review-grade quality alone creates no document blocker. Independent FAIL findings continue to block. Review message and action text reflect the grade.
- A5, R6. Every intentional old-test change appears in the approved expectation inventory. Additional regressions cover grade, message, blocker and integrated-review behavior.
- A6, R7. Paired v2 reports retain stable case membership and denominators. False acceptance increases in either defect group, either A/B stage, document type or condition trigger a stop and report. Also report any newly introduced PASS case even if aggregate counts offset it.
- A7, R8. Record actual results beside the supplied baselines of engine_v2 1,448 passed and 3 skipped, backend 1,252 passed, and 18 scenarios with 1,885 checks and zero failures. Identify count changes. Present frontend lint/build results and the main-relative diff before requesting commit approval.

## Scope boundaries

Outside scope are threshold changes, password-PDF handling changes, payment extraction changes, performance work and real-document measurement. Real-document remeasurement belongs to the user. The proposed application point is new uploads and explicit reassessment. Historical stored results receive no automatic migration in this task.

## Artifact and approval state

The user approved implementation and the original five-test expectation proposal, with a correction requiring quality FAIL when classification fails. The corrected expectation inventory contains four tests. Unknown cases in the parameterized quality test and the interleaved-title CLI test retain their existing FAIL expectations. Reported this reduction before implementation. Commit approval remains pending.
