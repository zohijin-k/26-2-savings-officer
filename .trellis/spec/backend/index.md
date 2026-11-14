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
| [Confirmed failure filtering](./failure-filtering.md) | Upload certainty, provisional continuity and submission blockers | Active |
| [Document OCR and Form Contracts](./document-form-contracts.md) | Resident-number redaction, coordinate forms, arithmetic, identity and review boundaries | Active |
| [Synthetic officer seeding](./officer-demo-seeding.md) | Fixed samples, demo-only ownership, idempotence and safe cleanup | Active |
| [Demo stage-two seeding](./seed-application.md) | Guarded developer CLI, shared validation, ownership cleanup and same-tab upload restoration | Active |
| [Private case verification](./verify-cases.md) | Shared upload assessments, ignored manifests, value-free snapshots and signed regression differences | Active |
| [Value-free batch assessment](./batch-assess.md) | Resumable per-document JSONL, local engines, policy-separated summaries and synthetic-only verification | Active |
| [Payment structure dump](./payment-structure-dump.md) | Exact constant-label masking, provider geometry, scoped value-free diagnostics and synthetic verification | Active |
| [DocumentAI measurement](./documentai-measurement.md) | Own-only observation, exact/CER denominators, synthetic matrix and private silver-reference safety | Active |

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
