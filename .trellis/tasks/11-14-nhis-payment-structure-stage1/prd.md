# NHIS_PAYMENT stage 1

## Goal

Explain NHIS_PAYMENT input-granularity failures and prepare value-masked structural evidence for a later extractor improvement. This task does not modify extraction behavior.

## Background

User-supplied aggregate evidence (no document values): among 275 payment certificates, monthly billed-amount extraction is 4.4% with own and 79.6% with Apple Vision. MISSING_BILLING_MONTHS also occurs on 111 text-layer PDFs. Synthetic measurement v2 shows 58 additional field losses with own versus the text layer. The working hypothesis is that line, region and word granularity differ across the three providers and affect header/column recognition.

## Confirmed code evidence

R1 investigation confirms that all three inputs expose OcrWord lists and `nhis_common.py:110` reconstructs lines uniformly. Government recognition/month rows require single-word month anchors (`nhis_payment_gov.py:24`, `:165`), nine ordered header clusters (`:134`) and non-crossing body-cell boxes (`nhis_forms.py:268`). The legacy reader has different header and period dependencies (`nhis_payment.py:104`, `:168`). MISSING_BILLING_MONTHS also covers independent period uncertainty/conflict (`demo/backend/rules/doc_check.py:395`), so it is not equivalent to a missing extracted month field. Existing focused tests passed 63 cases; synthetic probes refute a line-only contract but do not establish the measured real-document cause. See research/input-granularity.md for all evidence and caveats.

## Requirements

- R1: Research extractor header/column validation and monthly row recognition, trace text-layer/own/Apple Vision words, distinguish confirmed causes from hypotheses, and persist source anchors.
- R2: Plan a single-input structure-dump tool under engine_v2/tools using existing dump patterns where available. Preserve page, geometry, size and order for text-layer/own/Apple Vision; mask numbers to 9, Korean to 가, Latin letters to A and retain other symbols. Only whole words exactly matching a vocabulary derived exclusively from existing extractor module constants may remain literal.
- R3: Follow verify_cases location policy, print no paths, and validate non-leakage with synthetic documents only.
- R4: Plan batch_assess --ids <file> to select relative source paths while preserving existing resume and location behavior.
- R5: Do not use real documents or record their paths or filenames in any planning artifact. Do not request those details.
- R6: Do not change OCR, extraction or assessment runtime code or existing tests. Extractor changes belong to stage 2 after user-provided structure dumps.
- R7: Work on a new branch. User approved implementation on 2026-11-14 with the refinements below; preserve the separate pre-commit approval gate.
- R8: Add per-engine value-free extraction diagnostics: recognized allowlisted heading names, found/expected nine heading groups, recognized month count, failed validation names, and existing billing-check cause distinctions. Never include values or source text in diagnostics.
- R9: --ids reports counts only for inventory paths outside selection, duplicate entries, outside-root entries and missing/invalid entries. Exclude unusable entries, process only valid unique listed paths, and skip already completed IDs on resume.
- R10: Synthetic tests must prove every declared document-value sentinel (names, amounts, numbers and other values) is absent from console and every saved dump artifact.

## Acceptance criteria

- AC1: A source-backed research report, design.md and implement.md are ready for review before implementation.
- AC2: A synthetic dump example demonstrates the geometry/order contract and masking, including exact-label-only exceptions and value-free per-engine diagnostics.
- AC3: --ids processes only listed relative paths and preserves resume and output location policy.
- AC4: Before any commit, show git diff --stat main; four validation groups (engine_v2 baseline 1,448 passed / 3 skipped, demo/backend baseline 1,296 passed, 18 scenario modules baseline 1,885 assertions / 0 failures, frontend lint/build); and a synthetic structure dump example, then wait for commit approval. Record actual results and explain differences rather than rewriting expectations.

## Out of scope

Real-document inspection or batch execution; provider/model changes; extractor, verdict or operational behavior changes; existing-test edits; stage-2 fixes; commits before separate approval.
