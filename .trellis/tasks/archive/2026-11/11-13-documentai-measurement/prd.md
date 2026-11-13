# DocumentAI measurement

## Requirements
- Measure own OCR plus unchanged engine_v2 extraction and demo upload verdicts for resident abstract, NHIS payment, qualification, acquisition/loss and four-insurance enrollment.
- Cover original, monochrome, +5/-5/90 degree rotation, low resolution and phone degradation with independently authored synthetic truth.
- Report field exact accuracy and CER, independent document classification accuracy, confirmed reupload-code false rejection counts/rates on normal content, defective-document PASS rate and processing seconds/page.
- Provide a private text-layer-PDF agreement mode with a verify_cases-equivalent resolved location policy and value-free output. Do not execute it on real documents.
- Never open private source data; do not modify OCR, extraction, decision logic or existing tests. Execute only synthetic cases.
- Use a new local branch and coherent local commits; no push/PR/merge/main changes.
- Compare engine 1,264 passed/3 skipped, backend 1,252 passed, all 18 scenarios/1,885 assertions/zero failures and frontend lint/build.

## Acceptance
All 35 type/condition cells have explicit denominators and completed/error counts. Authored defects are separate. Numeric artifacts, readable tables, weak rankings, improvement candidates, decisions and regression results are committed. Private policy/privacy tests use fabricated PDFs and temporary Git repositories only.
