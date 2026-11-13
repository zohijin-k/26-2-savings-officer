# Bug analysis: persistent seed receipt namespace

## 1. Root cause category
E (implicit assumption), B (cross-layer contract), D (coverage gap). The original prototype assumed an empty application table implied an unused receipt namespace. Old synthetic tests can leave form archive files independently of DB lifecycle. The ordinary API also allocates count+1, which can collide with surviving receipt numbers after row deletion.

## 2. Why the fixes were incomplete
1. Guarding collisions prevented overwrites but rejected an otherwise valid local demo containing unrelated old synthetic exports.
2. Renaming after ordinary API create separated storage names but still allowed the API's earlier count-based UNIQUE collision.
3. Final fix: allocate only the new marked seed Application using a dedicated UUID receipt and latest criteria version before any files; keep all later API/engine handlers unchanged.

## 3. Prevention mechanisms
| Priority | Mechanism | Status |
| --- | --- | --- |
| P0 | Separate ownership receipt namespace, never delete unrelated collision files | Done |
| P0 | New regressions for orphan generic archive and surviving numbered row gap | Done |
| P0 | Snapshot/transaction protection for existing rows and owned-file rollback | Done |
| P1 | Document the shared DB/storage lifecycle and init_db backfill side effect | Done in backend/officer-demo-seeding.md |

## 4. Systematic expansion
The ordinary create API numbering issue remains outside this task; no API/model/engine code is changed. Fresh-temp tests alone did not cover persistent storage lifetimes, so the new tests include pre-existing artifacts and partial deletion. No templates directory exists in this application repository to synchronize. Commit is deferred to the user's explicit approval gate, overriding the skill's immediate-commit instruction.

## 5. Knowledge capture
Updated .trellis/spec/backend/officer-demo-seeding.md and frontend/officer-documents.md plus their indexes. No follow-up task or external issue was created because the user authorized this repository scope only.
