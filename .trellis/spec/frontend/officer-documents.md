# Savings officer application views

## 1. Scope / Trigger
Use for this repository's officer-only React entry: the application list (role switch, queue tabs, filters, bulk bar, reason rows), navigation, and inline review detail. Applicant and youth-job UI are absent; retained backend contracts do not authorize exposing their UI again. Program settings/info tabs and the sidebar menu from the 26-2-youth officer UI are intentionally not ported.

## 2. Signatures
- `pages/officer/list-model.ts`
  - `queueOf(row: OfficerRow): 'needs_review' | 'pass' | 'done' | 'rejected'`
  - `queueCounts(rows)` returns `{ needs_review, pass, done, rejected }`.
  - `matchesFilters(row, { search, from, to })` — search matches `application_no` + `name` (case-insensitive); `from`/`to` are inclusive `YYYY-MM-DD` against `submitted_at`.
  - `importanceOf(row)` counts documents needing a look: non-PASS originals plus required documents with `document_id === null`.
  - `sortRows(rows, 'importance' | 'latest' | 'oldest')` returns a new array; it never mutates rows.
  - `firstDocument(row)` returns the first non-PASS original `{ documentId, slotKey }`, else the first original, else `null`.
  - `collectOfficerList(loadPage)` loads every page and keeps the first page's `role` and `scope`.
  - `selectOfficerDocument(documents, documentId, slotKey)` selects an exact ID first; a missing explicit ID must not fall back to another file.
- `pages/officer/tiebreak.ts` — `tiebreakParts(sheet)` turns the backend tiebreak key into display text, or `null` when the key is absent.
- `api.ts` — `fetchOfficerRoles()`, `fetchOfficerList({ role, region?, town? }, page)`, `fetchReviewDetail(id, role = 'province')`, `postDecision(id, decision, memo, role = 'province')`, `postBulkDecision(ids, decision, memo, role)`.
- Canonical routes: `/officer`, `/officer/review/:applicationId?document=:documentId&slot=:slotKey`. Explicit preview uses `mock=1`. The role is kept in `sessionStorage` (`officer-role`), never in the URL.

## 3. Contracts
Read the officer list API with `program=double_savings`, `page_size=200`, the selected `role`, and `region`/`town` only when the role requires them (`requires_region` / `requires_town`). Send the same role to detail, decision and bulk-decision calls.

Queue classification is display-only: an officer `decision` of `reject` means `rejected` (반려 tab, placed after 처리 완료); any other decision means `done`; otherwise `ai_status === 'PASS'` means `pass`; every other value (`NEEDS_REVIEW`, `FAIL`, `null`) means `needs_review`. Never write saved verdicts while deriving a queue. Tab counts are computed after search/date filters.

Sorting is client-side within the shown tab. `importance` (default, 중요도순) puts more documents-to-check first, ties by oldest `submitted_at`; `latest` (최신순) and `oldest` (등록순) order by `submitted_at`, with undated rows last. The 사유 toggle shows the importance count. The list has no score column; scores appear in the detail 심사표 panel.

Bulk selection exists only when `role.can_bulk` and a bulk handler are present; the town role renders the checkbox column empty so column positions do not shift. The bulk bar replaces the filter row in place. Reason rows load the detail API on demand and render only stored values: non-PASS documents with their `findings`, required documents with `document_id === null` as 미제출, and application-wide `ai.reasons`. Do not invent explanations or recompute eligibility.

Detail must verify `program_code` before displaying a direct URL. The right panel order is 최종 판정 (AI 종합의견 card, AI 제안 vs 담당자 판단, fixed no-supplement warning, application-wide reasons) → 심사표 (total, tiebreak values, 서식6 with income marked 데모 추정치) → 판독 결과 for the selected document → 담당자 처리. Eligibility and exclusion panels stay out until the detail API returns those values.

Design tokens live in `src/index.css` (`--color-*`, status `-5/-10/-50/-60`, `--fs-*`, 4px `--space-*`). Logo accents (`--accent-*`) are decoration only. Pretendard GOV is bundled locally; `.form-sheet` keeps Malgun Gothic to mirror the paper form.

## 4. Validation & Error Matrix
| Input | Behavior |
| --- | --- |
| No decision, AI PASS | 적합 tab |
| No decision, AI NEEDS_REVIEW / FAIL / null | 확인 필요 tab, 사유 toggle shown |
| Officer decision `reject` | 반려 tab; 사유 toggle shows the stored decision memo first, then document reasons |
| Other officer decision (approve / hold) | 처리 완료 tab, chip shows `decision_label` |
| Role without `can_bulk` (town) | No checkboxes, no bulk bar |
| Role requiring region/town | Region/town selects from `scope`; changing them refetches |
| Multiple API pages | Fetch through `page_count`, then classify |
| Two documents sharing a slot | Selected document ID determines original |
| Missing explicit ID / original | Empty state, no silent first-document substitution |
| Applicant/criteria/other-role route | Normalize to `/officer` |
| Non-savings detail | Error without rendering its business UI |
| Empty API / failed API | Empty tab copy / error with 다시 시도; no automatic mock fallback |

## 5. Good / Base / Bad Cases
Good: a seeded all-PASS application appears only in 적합, a NEEDS_REVIEW application only in 확인 필요, and opening it lands on its non-PASS original. Base: refresh/back/forward retains the selected document and the session's role. Bad: bucketing by a single document status, or storing a queue value back to the API.

## 6. Tests Required
Run `npm test`, `npm run lint`, `npm run build` in `demo/frontend`, plus `pytest demo/backend/tests/test_officer_frontend_integration.py`. Native TypeScript tests require Node 22.18+; app development uses Vite's supported Node 20.19+/22.12+ environment. The backend integration test compiles the real `list-model.ts` and `ApplicationList.tsx` in memory with installed TypeScript and React, renders each queue tab from seeded API rows, and checks placement without changing saved rows. Preserve fonts TTF/WOFF2/OFL: backend forms and P7/P14 still depend on them.

## 7. Wrong vs Correct
Wrong: select the first `__unassigned__` document by slot, or change FAIL into NEEDS_REVIEW in storage. Correct: keep the document ID and source status; derive only the view queue. Wrong: put the role in the URL or let it change the review route. Correct: role stays in session state and is passed to API calls. Wrong: remove all `forms`/font assets with applicant UI. Correct: preserve officer ScoreSheet's shared FormSheet shell and backend font assets.
