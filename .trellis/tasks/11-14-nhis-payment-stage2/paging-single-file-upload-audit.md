# Upload contract audit and final paging decision

Read-only investigation requested after the first refinement review. Both repository codebases were accessible. The applicant checkout was explicitly authorized for read-only inspection; no file there was changed, no private documents were read, and no tests were run there.

| Contract | Officer checkout | Applicant checkout |
| --- | --- | --- |
| Explicit payment slot retains | One file: `demo/backend/api/documents.py:266` deletes the same slot's old rows, then `:338` saves the new one | Same backend contract at `documents.py:266`; frontend `DocumentUpload.tsx:410` displays the first document and `:908` replaces the slot list with `[doc]` |
| Request input | `upload_document` receives a single `UploadFile` | `DocumentUpload.tsx:452` takes `files[0]`, `:478` has no multiple attribute, `api.ts:448`/`:469` sends one `file` |
| Multiple image files accumulated in one slot | No | No; `upload-queue.ts:82` also replaces the pending entry for the slot |
| Automatic merged PDF path | Separate path; a second same-kind page can be unassigned | Same separate path; this is not multiple retained files in one explicit slot |
| PAGES_INCOMPLETE guidance | `doc_check.py:105`: “빠진 쪽까지 모두 올려 주세요.” | Frontend `reupload-guidance.ts:30–33`: “빠진 쪽까지 모두 올려 주세요.”; reason explains the printed total exceeds uploaded pages; fix includes “가능하면 모든 쪽이 들어 있는 PDF 한 파일을 올려 주세요.” |

Applicant paths are relative to `/Users/zohijin/Desktop/26-2-savings-applicant`; officer paths are relative to this checkout. Code inspection establishes the local contracts, not the identity of a deployed server.

## Corrected conclusion

The earlier inference “cannot aggregate split files, therefore apparent missing pages must always review” was wrong for this explicit-slot contract. The retained file is the slot's complete submission. Under the user's conditional instruction, restore PAGES_INCOMPLETE FAIL for a complete, reliable, consistent printed total greater than that file's physical page count. Do not aggregate files from a batch folder into an upload submission. Keep the nine prior FAIL expectations unchanged. A repeated upload replaces the first file and is assessed from the remaining file alone.

A counter still never supplies PASS: confirmed nonconflicting period, all required/printed-range months, observed matching totals and source issue fields are separately required for the paging-review exemption. Conflicting/unreadable markers cannot establish omission. C2 remains held.

## Guidance proposal only

The officer common guidance does not explicitly say one file. Proposed payment-specific wording: “납부확인서의 모든 쪽을 순서대로 한 PDF 파일로 합쳐 다시 올려 주세요.” No guidance text or applicant-checkout code was changed. Existing generic officer guidance and existing applicant guidance remain.

## Test disposition approved by the user

Of the historical 28-case inventory, the user approved 19 adjustments: five C2 positives retain their assertions under strict xfail with reason `C2 header-edge recovery held`; one local boundary token now actually crosses the expanded boundary and retains UNCERTAIN/token-preservation checks; twelve fallback expectations change; the main legacy-period case changes verdict, premium trust and pipeline assertions together. The other nine FAIL expectations remain unchanged and pass after restoring the single-file rule.

Added ten incomplete-table cases use the same five uncertain-marker/confidence variants in both routes and assert PG REVIEW, no FAIL and no new quality finding at adequate quality. Newly authored split-file cases now verify replacement plus remaining-file FAIL rather than invented aggregation. No common fixture, added 1/1 in the historical 26 cases, corpus input, truth or metric was changed.

## Final review fixes

Independent review found a split date could cross the horizontal region boundary and leave a false counter suffix. A whole-row connected date/money-run exclusion now preserves original tokens and prevents that adoption; a distant independent counter on the same row remains eligible. Separate tests first reproduced the wrong adoption.

Completeness proof now binds its source financial-field representations as well as monthly values and issue date. Changing an observed sum, paid total or monthly care map cannot reuse old arithmetic booleans. The five new boundary/stale-proof cases failed before and pass after; the complete refinement set passes. No source document values or coordinates appear in this report.
