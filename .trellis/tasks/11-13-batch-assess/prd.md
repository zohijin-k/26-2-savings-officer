# Value-free local batch document assessment

## Goal

Build `engine_v2/tools/batch_assess.py` to inspect a local document tree sequentially, retain only value-free measurements, resume after interruption, and print numeric aggregates without reopening documents.

## Background and authorization

- The user approved creating this task and planning artifacts on a new branch. Branch: `feat/batch-assess`, based on `main` at `1924a9b`.
- The user approved implementation on 2026-11-13 with six refinements incorporated below. Commit remains separately gated; no push or merge.
- Development and testing use newly authored synthetic inputs only. Do not locate, open, request or record actual document paths/names. Investigation stays inside the repository; documentation examples use fictitious paths only.

## Requirements

### R1. Discovery and locations

- `--root <directory>` recursively processes only PDF, JPG, JPEG, PNG, HEIC, GIF and JFIF, case-insensitively. Hidden files, files below hidden directories and other extensions are counted by extension without content reads or recording their names.
- The unchanged root-relative path is the document ID. Assign persistent numeric person-group IDs from the first directory component below root; root-level files use group 0. Grouping is organizational, not an identity assertion.
- `--out <directory>` applies `verify_cases` resolved external-or-ignored-and-untracked policy to directory and output targets. Reject source/output aliases. Discovery does not follow symlinks outside the supplied root.
- `--engines own [applevision]` requires own. Optional AppleVision unavailability is recorded as skipped with a fixed code. No fixture, remote engine, download or unrelated fallback.

### R2. Per-file records

Each completed supported file, including terminal processing failures, has one JSONL row containing only:

- Undecodable accepted formats including HEIC produce a fixed decode-error row and do not stop the run.
- Schema version, relative ID, group number, page count, pages with non-whitespace text-layer content, open-failure flag, fixed error code and validated exception class where applicable.
- Content-based detected kind without an expected upload slot. Own is the primary result; AppleVision also retains its independent detected kind.
- For work_proof, map only INSURANCE_4 to EMPLOYEE (직장가입자) and BIZ_REG_PROOF to BUSINESS (사업소득 사업자); other work kinds are NOT_ASSESSED with a fixed mapping-unavailable code. State this mapping in design and summary.
- Applicable upload slot, document status and reason code/severity pairs from `demo/backend/upload_assessment.py`, without database lookups/persistence. Classification/slot failure produces a fixed unassessed outcome, never an invented type or verdict.
- Identity check explicitly `미검사`: no authenticated identity is available, and none is inferred from OCR or other documents.
- Extracted field names; own/AppleVision field-presence O/X and agreement O/X; text-layer/own agreement O/X when every PDF page has text-layer content. Unavailable, failed and inapplicable comparisons are explicitly non-comparable, never a false O.
- Engine elapsed processing time, pages processed and seconds per page; no division by zero or fabricated page for invalid files.

### R3. Durable sequential execution

- One process, one file and one engine at a time. Append and durably flush each completed JSONL row immediately.
- Restart skips completed IDs, including completed error rows. An interrupted in-flight file has no completed row and is retried.
- Preserve valid prior rows, recover only an incomplete final record and reject corrupt interior rows, duplicates, unsafe schemas and incompatible root/engine settings without echoing contents.
- Group numbers survive restart/new groups. Exclusion counts describe the latest inventory instead of accumulating on each run.

### R4. Privacy and console

- Apart from permitted paths/filenames, never persist or print original content, extracted values, OCR strings, exception messages/tracebacks, confidence numbers, evidence/basis objects or value hashes. Compare values only in memory.
- Use positive vocabularies for kind/slot/status/reason/severity/field names; unknown metadata becomes fixed markers/counters. Arbitrary dependency keys are not safe field names.
- Suppress dependency Python/native stdout/stderr, logging and warnings, including imports. Block source/cache/debug/image writes, subprocess OCR, remote access and database connections.
- Batch console contains only progress counts and elapsed time. Fixed diagnostics/class names go to value-free artifacts where writing is safe; failures never echo arguments/paths.

### R5. Summary

- `--summarize --out <directory>` reads saved artifacts only; do not traverse root, import models or run OCR/assessment.
- Keep issuance/announcement/application-date reasons (including DOCUMENT_ISSUED_TOO_EARLY and DOCUMENT_ISSUED_AFTER_APPLICATION) in a separate 기준일 정책 사유 table. Do not mix these with classification, image quality, missing pages, extraction or agreement measurements.
- Show NOT_ASSESSED, SKIPPED and ERROR as separate rows; all rates show numerator and denominator. Print numeric tables with fixed labels: kind counts, classification failures, status distribution, reason-code counts, field extraction rates, own/AppleVision agreement, text-layer/own agreement and per-page timing distributions.
- Display counts and denominators. Two missing fields are not agreement; skipped/failed/unassessed populations remain visible, and zero-denominator rates are unavailable.

### R6. Scope and completion

- Add the tool, new synthetic tests and suitable docs/specs only. Preserve existing tests and OCR/extraction/classification/assessment/verdict/frontend operating code.
- Before commit, show `git diff --stat main`, new synthetic results and four regression branches: engine tests, backend tests, all scenario modules sequentially, frontend lint/build. Also show actual synthetic example summary output. Wait for separate commit approval; no push or merge.

## Acceptance Criteria

| ID | Observable outcome | Requirements |
| --- | --- | --- |
| AC1 | Nested synthetic inputs cover seven extensions, uppercase, hidden and unsupported entries; relative IDs and persistent groups are correct. | R1 |
| AC2 | Text/mixed/image PDFs, still/multiframe images, corrupt/encrypted files and unavailable engines produce all required measurements and fixed failure states. | R1–R2 |
| AC3 | Spies prove slot-free first classification, shared upload assessment with identity=None, and no database access. | R2, R4 |
| AC4 | Authored present/missing/mismatched/structured fields verify extraction/agreement denominators, absent-both X and non-comparable states; summary arithmetic matches independent expected counts. | R2, R5 |
| AC5 | Interruptions after a durable row and within a trailing row preserve prior data; restart gives one completed row per ID, skips error rows, and avoids duplicated exclusion counts. | R3 |
| AC6 | Synthetic sentinel names/dates/amounts/OCR/messages/malicious field names/evidence never appear in stdout/stderr or generated outputs/temporary artifacts; native/log noise and forbidden write/network/database attempts are tested. | R4 |
| AC7 | Synthetic Git fixtures inside this checkout verify external-to-fixture acceptance, ignored+untracked policy, tracked/unignored rejection, resolved symlinks/hardlinks and source collisions without opening anything outside this actual checkout. | R1, R4 |
| AC8 | Existing tests and production OCR/extraction/assessment files remain unchanged; actual four-branch results and diff against main precede commit approval. | R6 |

## Out of scope

Any multi-document income or work-continuity assessment; real-document execution; source rewriting/image or OCR dumps; identity comparison; person-level eligibility/income/cross-file verdicts; ground-truth accuracy claims; multiprocessing; remote engines; model installation; production-rule fixes; changing existing assertions; commit/push/merge before the stated review gate.
