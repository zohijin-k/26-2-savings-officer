# Savings officer document views

## 1. Scope / Trigger
Use for this repository's officer-only React entry, document grouping, navigation and inline review. Applicant and youth-job UI are absent; retained backend contracts do not authorize exposing their UI again.

## 2. Signatures
- `groupOfficerDocuments(rows: OfficerRow[])` returns `{ pass, needsReview }` of `OfficerDocumentRow` in `pages/officer/document-groups.ts`.
- `collectOfficerRows(loadPage)` loads every application page before grouping.
- `selectOfficerDocument(documents, documentId, slotKey)` selects an exact ID first; a missing explicit ID must not fall back to another file.
- Canonical routes: `/officer`, `/officer/review/:applicationId?document=:documentId&slot=:slotKey`. Explicit preview uses `mock=1`.

## 3. Contracts
Read the existing officer API with `role=province`, `program=double_savings`, `page_size=200`. Application `ai_status` is not a per-document classifier. Only document `status === 'PASS'` belongs to pass; every other value, including null placeholders, belongs to needsReview. Preserve source IDs, slot, required flag and original status. Never write saved verdicts while deriving a display group.

An application can have documents in both groups. Unassigned merged pages can share a slot, so IDs own selection. Missing originals render an explicit empty state. Detail must verify `program_code` before displaying a direct URL. Render findings `code`, `message`, `how_to_fix` from the existing response; do not invent a new explanation or recompute eligibility. Separate application-wide reasons from selected-document findings.

## 4. Validation & Error Matrix
| Input | Behavior |
| --- | --- |
| PASS document | Pass list |
| FAIL, NEEDS_REVIEW, null | Needs-review list; original value unchanged |
| Multiple application pages | Fetch through page_count, then group |
| Two documents sharing a slot | Selected document ID determines original |
| Missing explicit ID / original | Empty state, no silent first-document substitution |
| Applicant/criteria/other-role route | Normalize to officer list |
| Non-savings detail | Error without rendering its business UI |
| Empty API / failed API | Empty lists / error; no automatic mock fallback |

## 5. Good / Base / Bad Cases
Good: a mixed application contributes four PASS documents and one review document to separate lists. Base: refresh/back/forward retains the selected document. Bad: filtering applications by final AI status and calling that the document bucket.

## 6. Tests Required
Run `npm test`, `npm run lint`, `npm run build`. Native TypeScript tests require Node 22.18+; app development uses Vite's supported Node 20.19+/22.12+ environment. New backend integration test compiles the real grouping module and ApplicationList in memory with installed TypeScript and React, then checks seeded API rows in the actual rendered sections without changing saved rows. Preserve fonts TTF/WOFF2/OFL: backend forms and P7/P14 still depend on them.

## 7. Wrong vs Correct
Wrong: select the first `__unassigned__` document by slot or change FAIL into NEEDS_REVIEW in storage. Correct: keep the document ID and source status; derive only the view bucket. Wrong: remove all `forms`/font assets with applicant UI. Correct: preserve officer ScoreSheet's shared FormSheet shell and backend font assets.
