# Technical design

## Quality grade decision

| Source/evidence | Quality finding | Document outcome |
| --- | --- | --- |
| Existing unreadable-file condition | UNREADABLE_FILE FAIL | FAIL |
| Existing severe-resolution predicate | IMAGE_RESOLUTION_TOO_LOW FAIL | FAIL |
| Quality below cutoff and established essential-field unreadability | LOW_IMAGE_QUALITY FAIL | FAIL |
| Quality below cutoff and all applicable essential checks readable | LOW_IMAGE_QUALITY NEEDS_REVIEW | At least NEEDS_REVIEW |
| Quality below cutoff and document classification failed | LOW_IMAGE_QUALITY FAIL | FAIL |
| Quality meets cutoff | Existing non-quality findings | Existing grade merge |

The user explicitly requires LOW_IMAGE_QUALITY FAIL when below-cutoff quality coincides with classification failure, so applicants can reupload before final submission. Receipt OCR unavailability separately establishes unreadability of its required information and retains quality FAIL when below cutoff.

## Reuse existing assessment evidence

Keep `check_document` as the public single-document entry point. Finalize the quality grade after the existing essential checks and grade downgrades. Recognize explicit essential-unreadable findings and the existing branches documented in `research/quality-flow.md`. For ambiguous codes, retain a small internal readability observation at their existing decision branch if needed. Do not infer field unreadability from aggregate confidence or an identity mismatch. Do not build another field schema or extraction implementation.

The same quality finalization must run after consent/receipt postprocessing in `assess_upload`, so later required observations are included and reconstructed findings retain the quality warning. Repeated finalization must leave exactly one quality finding and recompute the overall grade from findings. Direct check_document callers still receive the finalized quality result.

Quality FAIL keeps the existing reupload guidance. Proposed review message is `화질이 권장 기준에 미달하여 담당자가 원본을 확인합니다.` Proposed review action text is `재업로드 없이 이대로 제출할 수 있습니다. 담당자가 원본을 확인합니다.` An explicitly readable-complete branch may additionally state that the required fields were read. Unknown-type low-quality results use the existing FAIL reupload guidance. The existing applicant projection hides review guidance when an independent FAIL remains.

## Submission-time agreement

Use one engine-owned `image_quality_status(score, classification_succeeded, required_fields_readable)` function from upload finalization and submission-time engine assessment. Its below-cutoff result is FAIL for failed classification or unreadable essential fields, and NEEDS_REVIEW for recognized documents with readable essentials. The score threshold stays in engine config.

Project existing saved findings internally through document_fact. The adapter derives successful essential readability from the explicit saved LOW_IMAGE_QUALITY NEEDS_REVIEW finding and successful detected type, then passes that evidence through defaulted engine Document inputs. Callers without assessment evidence retain conservative legacy behavior. No additional serialized finding or OCR-field keys are needed. Both single-document messages and stage1 grade aggregation call the same quality function.

A separate confirmed assessed-document failure signal preserves independent demo-specific FAIL precedence, including codes absent from the legacy engine enum. Root rechecking must not turn such a document into review solely because its quality finding is review-grade. Keep raw quality scores and complete stored findings. Add helper, adapter, real submission and officer agreement regressions, including legacy inputs.

## Compatibility and application point

Existing method signatures remain compatible through defaulted additions, if any. New uploads and explicit reassessment use the new conjunction. Existing stored findings without new assessment evidence keep their historical interpretation until explicitly reassessed. This task includes no automatic stored-result migration.

The officer-only UI already supports the target grade and uses API-provided text. Validate its real grouping and detail rendering. Applicant effects are verified through retained API contracts, because the current checkout provides the officer frontend only.

## Expected implementation surface

- `demo/backend/rules/doc_check.py` for conjunction, review floor and grade-specific guidance.
- `demo/backend/upload_assessment.py` for final receipt/consent observation ordering and quality retention.
- `demo/backend/api/common.py` for an internal saved-findings projection in document_fact.
- `demo/backend/engine_adapter.py`, `engine/models.py` and `engine/stage1_document_check.py` for the submission bridge.
- Focused backend regression tests and the approved existing expectations in `research/test-impact.md`.
- `.trellis/spec/backend/failure-filtering.md` for the accepted policy and submission contract after verification.

## Approval and rollback

Implementation and existing-test edits require approval of this plan and its expectation inventory. Additional old-test changes require a fresh file/test/before/after/reason report. Any increased false acceptance stops work for reporting. Before commit, present the required four verification branches and main-relative diff, then wait for explicit approval. Any rollback targets this task's code changes while retaining investigation and comparison evidence.

## User correction and approval

Implementation approved on 2026-11-14. Below-cutoff quality plus failed classification is FAIL. The corrected inventory contains four existing tests with changed expectations. Add explicit upload/submission parity tests for readable, essential-unreadable, unknown, OCR-unavailable and independent-FAIL cases. The before/after stop gate and pre-commit approval gate remain mandatory.

## Accepted alternatives and duplicate documents

Submission matching must retain a newly assessed quality-review alternative that the checklist accepts, even when its primary document type is absent. Use the existing accepted_doc_types with primary-type matching precedence and preserve actual detected types. Aggregate the shared quality rule across every explicit assessed quality context, including documents hidden by legacy type indexing. Preserve both review and FAIL outcomes and retain a grade-appropriate reason for contextual documents skipped by that indexing. Default callers without assessed context follow their existing matching path. This correction is part of the approved upload/submission parity requirement and adds regression cases without extending the four-function old-expectation inventory.
