# Review integrity and household discovery

## Scope and lifetime contract

Applicant submission may discover overlaps but must never update another Application or Review. Preserve officer memo, role, decision, decision time, engine result, payload and revision. Add directed links only to the new Review payload using `_append_household_link`, which preserves FAIL and deduplicates reasons. Do not skip an overlapping submitted Application just because it has no Review. Persist the source Review and its Application status in the same outer `BEGIN IMMEDIATE` transaction. A rollback must leave no reverse warning.

The existing policy scope is scored selection, same program, same `created_at.year`, non-draft candidates, and verified qualification member name plus birth. There is no intake-round model; criteria_version is a rules snapshot rather than a round. Do not invent administrative rules. Resolve round/year policy explicitly before production rollout.

Officer detail projects reverse warnings from persisted submitted-source Review edges via `_incoming_household_warnings`; existing decisions stay unchanged. Include related case numbers in the rendered messages, without household member names/birth dates in reverse warnings. The existing reason UI renders these messages. Applicant projections must continue hiding internal judgments and relationships. This does not introduce a new review queue or automatic reopening/approval.

## SQLite DML guards

Retain guard-v3 exact UPDATE (+1 revision) and duplicate INSERT definitions. Add hard DELETE rejection and immutable Review `(id, application_id)` UPDATE protection. INSERT protects REPLACE/UPSERT before any existing row can be removed. UPDATE identity protection also covers UPDATE OR REPLACE collisions. Never depend only on DELETE triggers: SQLite conflict replacement fires them only with recursive_triggers enabled.

Retain the reviewed parent Application using DELETE/INSERT/UPDATE guards. Cover both unique parent keys: `id` and `application_no`. In particular INSERT OR REPLACE with an automatic/new id and an existing reviewed application_no can delete the victim when recursive_triggers and foreign_keys are both OFF; checking only NEW.id is insufficient. UPDATE OR REPLACE from an unreviewed parent into a reviewed application_no is also forbidden. Ordinary parent field updates remain compatible.

Review identity stays permanent under these installed guards, so current CAS can continue using application_id + revision without a new token or column. Do not claim protection against privileged DROP/ALTER, old backups, divergent DB copies, or a restored token namespace. Those require controlled offline migration, writer shutdown, backup policy, and session/token invalidation before rollout.

Migration reserves the writer before schema inspection, adds revision without deleting old rows, validates exact guard SQL, and installs additive guards in one transaction. Wrong definitions fail closed. A missing guard is installed by the migration/startup path; there is no persistent historical tamper detector. Reapplying is idempotent. Interrupted DDL must roll back. No production migration is authorized by this task.

## Maintenance and fixtures

Do not add an online bypass or remove guards for seed cleanup. Existing maintenance/seed tools reject reviewed records before moving any files. Use a fresh isolated synthetic DB for a new fixture lifecycle. Construct unreviewed fixture rows when testing first submission; never DELETE a protected Review to prepare the test. Unreviewed seed cleanup retains its existing ownership/path/rollback guards. Offline administrative correction, retention/deletion and audit procedures require separate approval and design.

## Required verification

Use synthetic temporary databases and block external network calls. Test full previous-record snapshots, no-overlap/scope/status/decision cases, multiple edges, rollback/retry, simultaneous submission, FAIL precedence and reverse officer warnings. Test all recursive_triggers and foreign_keys 0/1 combinations, Review/parent INSERT OR REPLACE, UPDATE OR REPLACE, UPSERT, rowid aliases, ORM delete/merge/bulk, actual cascade, normal CAS, stale 409, missing 428, invalid 422, and genuine legacy schema migration/reapplication/interruption. Real mixed-version HTTP must use real blockers, pipeline and DB writes; disclose any stubs separately. Official CI must include `test_integrity_closure.py`.

Reference: https://www.sqlite.org/lang_conflict.html and https://www.sqlite.org/pragma.html#pragma_recursive_triggers.
