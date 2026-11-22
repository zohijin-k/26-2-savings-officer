# Review revision contract

A Review is one server-managed record per application. Its revision starts at 1,
including historical records migrated by `models._add_missing_columns`. Every
successful officer write increments it once, including repeated identical content
submitted explicitly with a fresh token. Failed/conflicting writes do not increment.
SQLAlchemy `version_id_col` also increments and checks other ORM changes/deletes,
including existing household-evidence invalidation. Administrative criteria version,
checklist fingerprint, and timestamps remain separate concepts.

## API

Authenticated officer detail and list responses include `revision` (null if no Review).
POST `/api/officer/applications/{id}/decision` requires JSON `expected_revision`.
Success includes the new `revision`. Tokens must be positive integers within the exact JSON/JavaScript successor range
(<=9,007,199,254,740,990); oversized untrusted tokens never reach SQLite binding.
Missing/null preconditions return 428 with
`detail.code=REVIEW_REVISION_REQUIRED`; invalid typed values use FastAPI 422.
409 with `detail.code=REVIEW_REVISION_CONFLICT` means the conditional write lost.
Other 409 business errors retain their existing meaning. Unknown request fields,
including an attempted client-assigned `revision`, are rejected. Authentication,
resource and policy guards run before any actual mutation. A request for a submitted
application without a Review returns the existing 400 and does not create a row.

Bulk POST `/api/officer/applications/decisions` requires `expected_revisions`,
a JSON object mapping every selected application ID to its observed revision.
Duplicates/extra/missing mappings fail. All rows share the existing outer transaction:
one conflict rolls back every member and its Application status changes.
Client transports also fail closed when detail/list tokens are missing or invalid
(including a new frontend pointed at an unversioned old API).
List UIs use the versions already displayed, never fresh versions fetched silently
at click time. Refresh and review a changed selection before requesting it again.

Youth generic detail/decision carries the same revision and uses the same writer,
including the legacy individual/bulk entry points. `GenericReviewChecks` is a
separate row protected by its existing evidence fingerprint and transaction;
confirming a document does not increment a Review revision. Generic final-state,
hold/reject reason and approval-evidence restrictions remain authoritative and
may return a business 409 before a stale token is examined.

## Storage and atomicity

The officer service executes `UPDATE review SET ..., revision=revision+1 WHERE
application_id=:id AND revision=:expected` and requires rowcount 1. That statement
and related Application changes commit together inside the existing SQLite
BEGIN IMMEDIATE reservation/savepoint helpers. No process-global lock substitutes
for the conditional update. ORM system writers also emit revision-qualified SQL;
bulk SQL bypassing this service/version mapping is prohibited. Seed cleanup deletes
only explicitly marked synthetic data and ORM deletes are version checked.
Submission never deletes/reinserts an existing Review to reset its token.

## Migration and deployment

`init_db` still calls the existing lightweight additive migration; no Alembic tool
is present. Only a synthetic DB was migrated during development. Under an explicit
SQLite writer transaction it checks for duplicates, adds `revision INTEGER NOT NULL
DEFAULT 1`, verifies integer positive values, and creates a unique application index.
Existing columns, memos, decisions and indexes remain. Reapplication is safe. Duplicate
historical rows or invalid revisions stop startup for manual reconciliation; nothing
is deleted, renumbered or merged automatically. ORM schema also has the uniqueness
constraint for newly created databases. Migration DDL failures roll back.

Before any real rollout: stop/restrict writes on every old server, back up the
SQLite database using SQLite backup API (include a verified restore rehearsal and
all related stored originals), inventory duplicate Review rows read-only, and rehearse
migration on that backup. Back up the app/schema versions and record the current
revision distribution. Deploy the backend with its migration as a unit; smoke test
old-request rejection, auth, two-connection CAS and normal saves before opening writes.
Deploy the paired frontends and force users to refresh/review. Old clients fail closed
with 428; never supply a default revision on their behalf. Mixed old/new backend
workers are unsafe: old code can still write without CAS. Never roll back to the old
unconditional writer while editing remains enabled. On failure stop writes, retain
current DB/files, then either fix forward or restore the verified backup with matching
app/files after explicit operational authorization. Do not drop revision/indexes or
reset versions during rollback. No operational migration/deploy was performed here.

## Editing and uncertain outcomes

The editor sends its baseline revision even after a preflight read. A real CAS 409
preserves memory-only input, reads the latest authorized state, displays the server
memo separately, and blocks writes until the officer explicitly confirms comparison.
A failed latest read cannot unlock the old version. Accepting the latest baseline
never sends a write by itself. Late/disposed responses and duplicate clicks retain
Phase 6D protections. Reauthentication preserves the mounted in-memory draft.
No new persistent memo storage is used. Native reload/crash destroys that draft after
its existing unload warning.

After a timeout/lost acknowledgment, GET compares desired values and the exact
expected+1 revision. Matching state recovers without a POST; otherwise comparison
and explicit action are required. CAS prevents repeating a successful old token,
but there is no durable operation ID/idempotency record. Identical values written
by another actor cannot establish authorship; a delayed request can still commit
before another same-token attempt, with at most one winning. Exactly-once effects
or a definitive operation audit are not promised. Reject recovery also retains the
existing limitation around public notice verification and avoids automatic resend.

No durable review audit-event table or actor identity distinct from the shared
password session exists in this baseline. Existing decided_at/officer_role and
other protected data commit consistently; no audit records are deleted. This change
does not claim complete actor attribution or distributed audit completeness.
Only the same SQLite file and these revision-participating paths are protected.
Different databases, mixed old servers, replication, distributed transactions,
production restore, real SSO/jurisdiction RBAC and real-device/screen-reader validation
require later work. PRODUCTION_NOT_READY remains.
