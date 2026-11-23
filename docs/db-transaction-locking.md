# SQLite transaction locking contract (Phase 4B-1)

## Supported deployment and transaction ownership

The product currently constructs a synchronous SQLite engine for `demo/demo.db`
in `demo/backend/models.py`, using SQLModel and SQLAlchemy with
`check_same_thread=False`. The verification environment uses SQLModel 0.0.44,
SQLAlchemy 2.0.57 and SQLite 3.54.1. No PostgreSQL implementation, configurable
remote database deployment or schema migration is introduced by this change.
The existing SQLAlchemy QueuePool remains in use; WAL is not enabled here.

`session_transaction()` checks the actual engine dialect, obtains a connection,
sets its SQLite `busy_timeout`, and executes a real `BEGIN IMMEDIATE` before
reading state used to authorize a mutation. The outer context owns the real
commit or rollback and retains SQLite's database-file writer reservation through
that boundary. SQLite serializes writers for the entire database, including
unrelated applications; this is not a row lock or a PostgreSQL performance claim.

`get_session()` binds an inner ORM session to that outer connection with
`join_transaction_mode="create_savepoint"`. An inner `Session.commit()` releases
its savepoint and does not commit the outer transaction. A failed ORM flush
rolls back its savepoint without releasing the outer writer reservation, allowing
file restoration before another writer starts. Nested service composition must
join explicitly (`join_existing=True`) and propagate failures to the owner.
Default nested `session_transaction()` calls are rejected.

`transactional_write` wraps short synchronous mutation handlers before their
state and policy reads. Application-number allocation and insertion, applicant
input/identity/consent/context/subsidy changes, submission, officer decisions and
bulk decisions participate. Household-overlap updates during submission share
the same database transaction. Pure assessment helpers do not persist reviews.

## Local file guards and lock ordering

Existing per-application OS file-lock guards (`flock` on macOS/Linux,
`msvcrt.locking` on Windows; lock directory
`<temp>/jeonbuk-application-writes-<uid or win-user-hash>/`) remain useful for
local request preparation and composition. Their namespaces still differ between repositories
and may differ between workers. They are not the cross-process integrity source.
For normal guarded calls the order is file guard, then SQLite transaction.
If a composed service already owns the context-local database connection,
`application_writes.py` skips acquiring another file guard. This avoids waiting
for a file guard in the reverse database-to-file order. File guards are retained
on disk; their paths must not be unlinked while workers may be waiting.

## Upload, submission and deletion boundaries

Upload byte preparation and OCR run before acquiring the SQLite writer. UUID
upload paths preserve prior original bytes instead of overwriting a slot's file.
The upload records the prepared `Application.model_dump()` and ordered
`SubsidyItem` rows. After acquiring the writer, it reloads the current Application,
checks that it is still draft, and compares both prepared inputs. Changed draft
inputs cause HTTP 409 and discard the staged upload; the client must prepare a
new upload. The code does not silently save an assessment based on stale inputs.

Within that same reservation, slot replacement, document insertion and required
NHIS cross-document refresh complete before the real commit. A submission that
commits during OCR causes the late upload to return 409. Conversely, submission
must wait or time out when upload finalization already owns the writer. Multiple
processes cannot interleave the protected final draft check and slot mutation.
The uploaded-document lookup used during preparation supplies alternative-slot
suggestion text; persisted NHIS pairing is refreshed from current rows inside
the reservation. Submission evaluates current blockers and review state while
owning its reservation, including its written-form archive snapshot.

Deletion reloads the current draft/checklist inside its transaction, stages the
original by a reversible rename through `stage_file_deletion`, then changes the
DB. On a catchable failure the transaction restores the staged original before
rolling back and releasing the writer. Successful commit is followed by best
effort tombstone cleanup; cleanup failure does not report a failed logical delete.
Generated signatures and form archives use `preserve_file_on_rollback` to restore
prior bytes (or remove newly created outputs) before DB rollback. Their image
preparation occurs outside the writer where applicable, followed by a fresh draft
check at actual file mutation. These mechanisms are normal-exception recovery,
not durable journal or power-loss recovery.

## Waiting, cancellation and API errors

Synchronous writes apply a 5,000 ms SQLite busy timeout. Async finalization uses
`async_session_transaction()`: each `BEGIN IMMEDIATE` attempt has busy timeout
zero, releases its connection on contention, and yields to the event loop before
retrying, with an overall 5,000 ms deadline. There is no detached thread left
waiting to acquire the writer after request cancellation. After acquisition an
explicit cancellation checkpoint precedes finalization. The final mutation block
contains no ordinary await; a propagated cancellation rolls it back.

SQLite BUSY/LOCKED produces a sanitized retryable HTTP 503 with `Retry-After: 1`.
A SQLAlchemy pool timeout also maps to that availability response. Other SQLite
operational errors produce a sanitized 503 without promising automatic retry.
Unsupported dialects fail closed with 503. Business state/input conflicts use
409; existing validation and authorization contracts remain in place. Exception
SQL, database paths and parameters are not returned to clients.

The async retry loop covers SQLite contention after acquiring a connection.
QueuePool acquisition itself remains synchronous: pool exhaustion can block that
entry point and its cancellation latency was not tested. The local synchronous
file guard also retains its existing wait behavior. This change is not a promise
of bounded latency for every request phase or multi-worker authentication state.

## Verification and limits

Synthetic spawned-process tests call real mutation handlers with separate temp
file-lock directories and the same SQLite file reached through identical,
symlink and relative paths. Explicit synchronization events cover final status
read versus submission, same-slot replacement contention/retry, submission versus
deletion, submission during OCR, and rollback followed by another process retry.
Concurrency fixtures stub OCR/eligibility and store only NEEDS_REVIEW; existing
HTTP policy, ownership and document regressions provide independent coverage.
Failure tests cover outer commit, OCR/flush exceptions, async HTTP cancellation,
generated files, unsupported/unavailable databases, and staged-original restore
while a separate SQLite connection still cannot acquire the writer.

The supported evidence is same-host, separate-process access to a shared real
SQLite file on a filesystem with working SQLite locking, with compatible schema,
common document storage and every participating writer using this contract.
Distinct temp directories are not proof of a multi-host or network-filesystem
deployment. Memory databases are not a cross-process coordination store.

Officer and youth must not be assumed safe to point at one product database:
models, policy registries, extra tables and storage assumptions differ. Their
whole-product shared-schema compatibility was not established. Services using
different databases do not coordinate through these transactions; they require a
separately designed common coordination store or concurrency service. No database
consolidation is attempted.

No multi-host test, hard-kill/power-loss atomicity, durable upload journal/outbox,
immutable submitted-original version manifest or crash orphan cleanup is claimed.
A writer that bypasses the protected contract can still violate application
invariants. The existing process-local officer session/revocation behavior is a
separate deployment limitation. Do not infer production readiness from synthetic
locking verification.

References: [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html)
and [SQLAlchemy external transaction integration](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites).

## Repository-specific behavior

Savings officer preserves its existing applicant API, document assessment and
officer decision policies. Its synthetic seeding tools rely on the shared
transaction helper rather than issuing a duplicate `BEGIN IMMEDIATE`. No youth
generic-program models or policies are copied into this repository.
