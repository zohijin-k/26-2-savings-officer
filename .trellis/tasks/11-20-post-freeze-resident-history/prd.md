# Recover multi-page resident address history

## Goal

Recover readable continuation-page address history from split OCR table headers and prevent unread continuation tables from establishing a successful residence assessment. Preserve established decisions for unaffected documents.

## Confirmed evidence

- Frozen base: `bdd8aade18cd0885ad7549011af5b21241c344b8`; annotated tag `engine-freeze-1120` resolves to it. Working branch: `fix/post-freeze-resident-history`.
- User-provided value-free diagnostics: PDF/processed pages both 2; page-one entries 8; page-two number and date/holder terms seen, but not on one OCR line; two date-column words; no detected table or added entries; total 8, no history uncertainty, final PASS. This establishes detection failure, not the respective contributions of OCR segmentation and printed form.
- `engine_v2/extractors/resident_abstract.py:291` requires same-line header terms. `:425` and `:600` record empty history pages only after table detection. `:543` checks consistency of parsed history without accounting for undetected continuation tables.
- `demo/backend/ocr/localocr.py:219` maps number/empty-page signals to history uncertainty; `demo/backend/rules/doc_check.py:997` already provides the review-only `ADDRESS_HISTORY_INCOMPLETE` finding.

## Requirements

| ID | Requirement |
|---|---|
| R1 | Recognize nearby split headers only when vocabulary, vertical proximity, horizontal column order and body-row evidence jointly establish address history. |
| R2 | Recover every supported entry without inventing dates, ordinals, addresses or missing-page content. |
| R3 | Detect likely unread tables and incomplete candidate-row coverage. Prevent PASS on surviving partial history; use NEEDS_REVIEW unless an independent confirmed FAIL remains. |
| R4 | Preserve unaffected one/two-page decisions, notes, blank-page exclusions and duplicate/missing-page protections. Neither multi-page count nor an unrelated attachment establishes incomplete history. |
| R5 | Support only uniquely justified joining of observed date fragments; no character correction or cross-row guesses. |
| R6 | Verify through new synthetic cases, unchanged existing tests, full engine/backend suites, 18 scenario modules repeated sequentially, frontend checks, 410 pairs and G1/G2/INS4. |
| R7 | Stop further implementation on an existing-test failure or increased false acceptance; report cause and impact without changing expectations. |
| R8 | Per the user's 2026-11-21 follow-up, diagnose compatibility of the two existing temporary diagnostic scripts using synthetic inputs only. Preserve both originals, expose engine failures honestly and provide verified versioned commands if needed. Never execute the real numbered case. |

## Acceptance Criteria

| Case | Observable result | Requirements |
|---|---|---|
| A | Complete one-page history and its existing verdict remain unchanged, including the existing single-entry policy. | R4 |
| B | Normal two-page synthetic input yields exactly 8 + 2 = 10 entries, correct provenance and unchanged valid verdict. | R2, R4 |
| C | A nearby two-line continuation header yields the same ten entries when sufficiently supported. | R1, R2 |
| D | Ambiguous continuation creates no guessed entries or prior-row mutation, marks history incomplete and reaches NEEDS_REVIEW in engine/backend absent independent FAIL. | R3 |
| E | Unrelated prose/tables, scattered matching words and reordered columns create no history or new history-review signal; preserve existing page-policy outcomes. | R1, R4 |
| F | Test split header labels separately from date values. Only unique, adjacent, calendar-valid fragments recover; conflicting, cross-column/row or invalid dates are never fabricated. | R5 |
| G | Duplicates, ordinal damage, omitted pages, numbered notes and cross-page continuations retain protections. Combined independent confirmed issue-date/identity/page FAIL remains FAIL. | R3, R4, R7 |
| H | OCR lookalikes, scale/skew and location variations do not manufacture history or increase false PASS; unsupported layouts with structural evidence require review. | R1, R3 |

User-supplied comparison targets: engine pytest 2755, backend pytest 1861, 18 scenario modules with zero failures, own false acceptance 0/235 across 410 pairs, G1 25/25, G2 165/165, supplementary INS4 25/25. These are not results of this task; new tests may increase counts. Report G1/G2 presentation and validation sets separately.

## Constraints and exclusions

- The user explicitly approved this PRD/design/implementation sequence for execution on 2026-11-20. Priority is split-header recovery, then omitted-table uncertainty, then date-value concatenation only if its necessity is demonstrated. Preserve the review boundary for material scope/design changes.
- One Codex task, no concurrent agents. Preserve both original branches, frozen commit and tag.
- No real-document PDFs/images, individual rows, labels or holdout results may be inspected or executed. Do not modify existing holdout results or print real source text, personal information or business names.
- The user alone will execute real case 81. Later provide its verified local diagnostic method without running it. Historical 148/150 must never represent independent performance of the new version.
- Maintain `JBAI_ALLOW_REAL_DOCS=false`; no external OCR requests, new model installation, weight changes or retraining.
- Do not change existing test expectations without approval, unrelated functionality, DB, frontend design or demo screens.
- No amend, push or commit coauthor trailer. Stage each file individually and verify zero occurrences of all five user-specified forbidden literals in staged diff.
- Commit only after successful checks and the applicable Trellis commit-review gate, using `fix: recover multi-page resident history and flag incomplete tables`.

## Planning status

No unresolved product decision blocks review. Pin geometry thresholds with synthetic boundary tests before production edits; insufficient evidence always requires abstention/review. Technical proposal and execution details are in `design.md`, `implement.md` and `research/code-paths.md`.

Implementation reporting must aggregate PASS-to-NEEDS_REVIEW, NEEDS_REVIEW-to-PASS, FAIL-to-PASS, PASS-to-FAIL and all other transitions without printing document keys or source values. The H 150 labels/measurements are excluded from development, tuning and regression.
