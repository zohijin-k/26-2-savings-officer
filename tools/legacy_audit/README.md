# Phase 4A historical document risk audit prototype

This offline prototype is **SYNTHETIC_ONLY / PRODUCTION_NOT_READY**. It never
changes an administrative verdict. No server routes, application screens, models,
sessions, migrations, OCR, engine rules or deployed configuration are modified.

From the isolated repository root, using the existing backend dependencies:

```sh
python -B -m tools.legacy_audit.synthetic
python -B -m tools.legacy_audit --fixture /private/tmp/phase4a-synthetic-REPLACE
python -B -m pytest -q tools/legacy_audit/tests
```

The first command creates a fresh private temporary fixture and prints its path.
Only explicitly provided sealed synthetic fixtures are accepted. There is no
connection URL, production database option, automatic snapshot discovery or
runtime environment lookup. Do not relabel or copy operational data into a
synthetic fixture. A marker/hash is an integrity gate, not proof of anonymization
or a security boundary against someone deliberately forging a fixture.

## Architecture and repository policy

`core.py` contains immutable normalized records and pure classification functions.
`policy.py` maps built-in requirements using the existing pure checklist builder
and the application's recorded context/criteria version. It does not import
`api.common`, `rules.criteria`, `models` or session initialization. Missing criteria
or dynamic work/subsidy context yields unknown requirements, not default safety.
The built-in bankbook remains required despite its `upload=False` presentation.
Electronic form/consent fulfillment is outside this document metadata audit.
No document quality, eligibility, field or OCR rule is recomputed.

In youth only, `posting_<id>` requirements come from that application's
`ProgramApplicationSnapshot.snapshot_json.requirements`, with posting ID binding.
They never fall back to a mutable ProgramPosting or another application's snapshot.
Frozen generic form values, criteria and human checks are not re-evaluated.
Officer has no generic application/snapshot models; its adapter rejects generic
requirements as unknown. The repository discriminator is the only source difference
between copies. Shared rules should remain synchronized through explicit review.

`sqlite_reader.py` selects metadata columns, never identity, application number,
OCR content, review payload, scores, memo or actual payment amounts. Snapshot reads
extract requirements only. `SELECT * ... LIMIT 0` obtains schema column names
without fetching row values. The connection uses `mode=ro&immutable=1`,
`query_only=ON`, disabled extensions, `trusted_schema=OFF`, and an authorizer
allowing only SELECT/READ/FUNCTION/RECURSIVE. DML, DDL, ATTACH, writable PRAGMAs,
transactions and migrations are denied. Immutable mode is appropriate only for
sealed inactive synthetic fixtures here. Both pre- and post-run integrity checks
reject changed inputs, sidecars, symlinks, hardlinks and paths outside the fixture.
Files are synthetic byte placeholders; they are never parsed as PDFs or OCR input.

`synthetic.py` is a separate, explicit fixture writer. It creates actual repository
SQLModel tables on a new temporary engine, never the default model engine,
`get_session` or `init_db`. Youth's additional GenericReviewChecks DDL is included.
The writer is never imported by the runtime audit. Tests check actual model column
parity and verify fresh-process audit imports do not load ORM/API/OCR/engine modules.

## Actual storage and evidence limits

| Fact | Both repositories | Youth-specific |
|---|---|---|
| Application | id, program_code, criteria_version, status, created_at, updated_at, submitted_at | posting_N program codes |
| Document | id/application_id/slot_key/doc_type/expected_doc_type; stage1_status; uploaded_at; file_path; source_file_path/page_index | same Document fields |
| Aggregate result | Review.final_status, distinct from Document.stage1_status and officer_decision | generic Review has criteria outcomes, no built-in score contract |
| Original version history | no Document.updated_at, source hash, submission hash, version FK or append-only mutation log | same absence |
| Other hashes | officer ReviewSummary.input_hash is an AI-summary input projection, not an original hash | ProgramForm.confirmed_hash is a form-template hash; GenericReviewChecks.checks_json fingerprint binds a mixed current human-review state, not independently the submitted original |
| Snapshots | written_forms_archive_path/count archives generated forms, not all uploaded originals; ProgramCriteriaVersion preserves criteria | ProgramApplicationSnapshot freezes application-owned form/document/criteria configuration |
| Officer note | Review.officer_memo/decided_at and Application.updated_at; legitimate changes occur after submit | reject_notice is separate applicant-facing text |

Review payload document IDs/file_ref values point to current rows and endpoints;
they do not cryptographically bind verdicts to the original bytes. Review rows can
be modified; their timestamps do not provide a complete historical verdict log.
All *stored* final_status=PASS rows are conservatively considered, even when another
stored review is FAIL. An overwritten/deleted historical PASS cannot be recovered.

Before Phase 3B, built-in uploads could overwrite a basename and replace Document
rows; deletes could remove original bytes while Review PASS remained. Current UUID
paths preserve some superseded bytes, but deleted/replaced rows have no durable
version relationship to submission. Neither current bytes, current mtime nor UUID
presence reconstructs the historical original. This audit does not use mtime.
Application.updated_at is deliberately not source mutation evidence: notes,
workflow and re-review can change it. Document.uploaded_at after submitted_at is
suspicion, never proof. Mixed timezone bases are unknown.

The auto upload path may leave `auto`/`unassigned`, source_file_path/page_index or
`_merged` path components. Assigned merged pages are included, even if they now
occupy explicit valid slots with document PASS. Missing provenance can conceal an
old auto upload; absence of these markers does not prove explicit upload. Built-in
review excludes unassigned rows; generic review trusts assigned stored document
PASS and requires every document to pass. Phase 3A's actual low-quality assigned
photo PASS counterexample is the basis for the merged+aggregate-PASS rule.
No timestamp cutoff is invented: all surviving markers are review candidates,
not proof of exact upload date, bypass causality or an incorrect administrative decision.

## Risk rules and counting

| Grade | Rules |
|---|---|
| CRITICAL | Independently submission-bound original version hash differs from current bytes |
| HIGH | Legacy auto/unassigned/merged markers coexist with any stored aggregate PASS; or required-slot/file/type/duplicate inconsistencies coexist with aggregate PASS |
| REVIEW_REQUIRED | Legacy markers, unassigned/duplicate/unrecognized slots, missing required document, non-PASS required document, incompatible or missing type evidence, invalid/missing file, post-submission uploaded_at, unproven completeness with aggregate PASS |
| UNKNOWN | Missing original history, invalid/ambiguous external proof, missing/malformed metadata, missing requirements/review/submission time or incomparable timezone bases |
| NO_FLAG_FOUND | No implemented signal; **not a safety PASS** |

Every signal is retained once per application; the highest grade determines the
application's one grade. Signal counts overlap; grade counts sum to inspected
applications. UNKNOWN also requires evidence review. Orphan document/review rows
are separate collection counts with a collection-review flag, never assigned to
an invented applicant. Audit grades and review-required flags never update Review,
Application.status, officer_decision, Document or an audit-log table.

The existing schemas have no trustworthy submitted-original baseline, so their
ordinary records retain HISTORICAL_ORIGINAL_UNVERIFIABLE. Synthetic normal cases
with NO_FLAG_FOUND have **additional synthetic independently preserved versions**.
`VersionProof` is an explicit normalized evidence interface, not a claimed schema
field. The synthetic sidecar binds application/document/submitted_at and a separately
preserved version, verifies the version hash, then hashes current synthetic bytes.
Invalid binding or absent files yield uncertainty. CRITICAL validates this proof
rule in synthetic data only. Production evidence authenticity, chain of custody,
time zones and version/event authority require a separate approved adapter.
No rule claims direct proven auto-bypass-to-incorrect-PASS causality from current
metadata. It is HIGH coexistence, not CRITICAL certainty.

## Output, validation and privacy

The CLI outputs aggregate counts only. Per-case core results contain only internal
synthetic IDs and closed reason codes; there is no CLI detail/identifier export.
No identifiers are merely hashed and called anonymous. Canary fixtures put private
synthetic values in identity, form fields, OCR and memo; tests require none in output.
Fresh-process audit tests deny network and forbid ORM/API/OCR/engine imports.

Tests cover the 16 requested scenarios, assigned merged PASS, historical stored
PASS with later FAIL, bankbook and conditional work slots, wrong types/duplicates,
orphan relationships, version/proof binding, missing schema and missing generic
snapshot, raw DB/path/symlink/seal/foreign-repository rejection, repeated execution,
all-table logical contents/counts, whole DB bytes and every fixture file hash.
SQL mutation attempts must fail. Existing backend regression logs are private
evidence; no full engine or UI change is required for this standalone tool.

## Future operational audit procedure (not enabled here)

1. Obtain approval and an access scope; take consistent DB and file backups.
2. Stop writes or use a proven coordinated snapshot protocol; include WAL and file
   version references correctly. Verify DB/file restore and integrity separately.
3. Create an isolated read-only snapshot with restricted credentials, no external
   network/OCR/LLM, no runtime app startup/default seeds or automatic migrations.
4. Establish approved repository/schema/policy versions, path mapping, evidence
   provenance, submission times/time zones and a documented unknown-state policy.
5. Implement and separately approve a snapshot-only adapter. Do not bypass this
   prototype's synthetic gate. Re-verify DB-native read-only grants and no writes.
6. Run aggregate audit; compare hashes/counts/statuses/verdicts/logs before/after.
7. Keep affected-application mapping in a separate access-controlled internal store;
   publish aggregates only. Define retention, access logs and evidence custodians.
8. Design an authorized processing hold for flagged historical applications;
   preserve existing PASS and administrative state until separately approved.
9. Officers review sources and reasons; decide whether originals can be recovered
   from trustworthy versions/backups. Re-review alone cannot recover lost history.
10. Document a correction proposal and audit trail; execute corrections only under
    separate approval, then revalidate, retain rollback material and monitor.

## Phase 4B and P1 handoff

P0-1: `demo/backend/application_writes.py` in both repositories: define DB ownership
and one serialization contract. Officer hashes a canonical SQLite filename and uses
no suffix; youth hashes a canonical SQLite URL and appends `.lock`. Even a shared
host/temp root will not serialize the two services sharing one DB. Disallow that
deployment until DB-native row/advisory/transaction locking is implemented for all
writers and submission paths (`applicant_access.py` / `generic_access.py`,
`api/documents.py`, `api/review.py`, youth `generic_programs.py`). Test separate
processes/hosts, UID/temp isolation, cancellation and lock-order/deadlock behavior.

P0-2: `models.py`, `api/documents.py`, `api/forms.py`, `api/review.py`, youth
`generic_programs.py`: immutable original-version rows and submission manifests
binding content hashes, archived form versions, criteria and review basis. Preserve
prior IDs/events; validate explicit retention and access policies. No automatic
history invention or backfilled certainty for old records.

P0-3: durable operation journal/outbox and idempotent reconciliation for UUID upload
orphans and `.pending-delete` tombstones. Define intent, staged-file fsync/rename,
DB commit and cleanup recovery order. Add fault injection at each boundary with
SIGKILL/restart, restoration, rollback, orphan reconciliation and monitoring.
Normal exception rollback is not power-loss atomicity. Never delete unreferenced
files automatically without retention/provenance and separate approval.

Then separately address date semantics (`rules/criteria.py`, `rules/doc_check.py`,
`upload_assessment.py`), PDF codec/inline rendering (`api/files.py`, protected
frontend DocumentViewer), form ownership/403 (`api/forms.py`, access middleware),
and officer responsive layouts. UI integration follows the current 400/409,
authorization, neutral applicant projection and read-only submitted contracts,
with synthetic E2E for the savings/job-package applicant and officer screens.
Keep the submission/freeze tags and separate applicant repository intact.
