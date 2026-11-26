# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | To fill |
| [Error Handling](./error-handling.md) | Error types, handling strategies | To fill |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | To fill |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | To fill |
| [Income and age eligibility](./income-eligibility.md) | Tri-state membership, exact income bounds, age and final-review consistency | Active |
| [Applicant submission](./applicant-submission.md) | Public reupload allowlist, neutral statuses, shared server submission checks | Active |
| [One backend for both frontends](./unified-backend.md) | Linked run topology, applicant projection boundary, stored-verdict test rule | Active |
| [Access control](./access-control.md) | Owner cookie on applicant routes and originals, officer login, middleware order, test helpers | Active |
| [Confirmed failure filtering](./failure-filtering.md) | Upload certainty, provisional continuity and submission blockers | Active |
| [Document OCR and Form Contracts](./document-form-contracts.md) | Resident-number redaction, coordinate forms, arithmetic, identity and review boundaries | Active |
| [Scanned resident completeness](./resident-scan-completeness.md) | 11-26 temporary no-auto-PASS guard for OCR-read 초본, end evidence, audit field and re-allow conditions | Active |
| [Officer reason projection](./officer-reason-projection.md) | 11-27 response-time mapping of stored stage1 reasons to each document's actual review reason; scan completeness vs OCR confidence; audit origin | Active |
| [Synthetic officer seeding](./officer-demo-seeding.md) | Fixed samples, demo-only ownership, idempotence and safe cleanup | Active |
| [Demo stage-two seeding](./seed-application.md) | Guarded developer CLI, shared validation, ownership cleanup and same-tab upload restoration | Active |
| [Private case verification](./verify-cases.md) | Shared upload assessments, ignored manifests, value-free snapshots and signed regression differences | Active |
| [Value-free batch assessment](./batch-assess.md) | Resumable per-document JSONL, local engines, policy-separated summaries and synthetic-only verification | Active |
| [Payment structure dump](./payment-structure-dump.md) | Exact constant-label masking, provider geometry, scoped value-free diagnostics and synthetic verification | Active |
| [DocumentAI measurement](./documentai-measurement.md) | Own-only observation, exact/CER denominators, synthetic matrix and private silver-reference safety | Active |
| [OCR baseline measurement](./ocr-baseline.md) | Page OCR/field agreement, symmetric masking, payment tables and private resumable metrics | Active |
| [Own adapter diagnostics](./own-adapter-diagnostics.md) | Original extraction/replay, conservative cause evidence, closed outputs and explicit denominators | Active |
| [Officer AI summary](./officer-summary.md) | 전북AI 종합의견: allowlist projection, scrubbing, grounded check points, rule fallback, cache | Active |
| [Per-document timing](./doc-timing.md) | Production upload path, delegation-only stage wrappers, cold start, warm-up/repeat statistics and value-free outputs | Active |
| [Classification recovery diagnostics](./classify-recovery-diag.md) | Existing-result crosstab, LocalOcr exit and cause codes, shadow-only candidate rules and value-free outputs | Active |
| [Blind label review](./label-review.md) | Localhost-only blind labeling for B/C, fixed samples, code-only labels and Clopper-Pearson summary | Active |

---

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.

- [Review integrity and household discovery](./review-integrity.md): lifetime DML guards, cross-application preservation, mixed-version tests and seed retention.
