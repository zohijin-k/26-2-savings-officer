# Synthetic Review safety CI

PRODUCTION_NOT_READY. No deployment, environment binding, production DB, secrets or real documents. External OCR/LLM is disabled; Python tests block network and SQLite outside the synthetic root. Official Actions are pinned to full commit SHAs; contents read, persist-credentials false and npm lifecycle scripts disabled. Python transitive dependency hash locking and mature secret/dependency scans remain Phase 6E work.

Results are three separate lanes, each with backend and frontend jobs:

- `event`: actual GitHub PR merge ref (`github.sha`), or exact push SHA. Prints PR number, event head/base/merge, tested SHA/tree/parents. This is CI-PR evidence while the workflow PR remains open.
- `contract-candidate`: immutable contract-inclusive candidate e96afc7a46d65024852a2761d12c7b0b574ef17c. This is not an advanced remote CAS branch HEAD until the contract PR is approved and merged.
- `candidate-main`: latest fetched main plus that immutable candidate, using a normal local merge. Prints the main SHA and tested merge tree. Merge commit SHAs may differ across jobs because local commit metadata varies; source trees and parents identify the integration.

Original CAS source 901690fe685c7b050d3d8a6405dbcd6a68c797be was tested by earlier runs; those successes do not prove these new candidates. Current lanes deliberately stop when CAS source lacks its bulk 422 correction or required CAS tests. Existing CAS PR checks remain independent: these workflow PR results never manufacture or replace them. After authorized main integration, verify actual CAS PR check attribution and source SHA anew. Required-check/protection settings are not changed.

Bulk regression validates every map value and complete Review/Application invariance for rejected input: 428 missing preconditions, 422 strict types/ranges, 409 stale valid tokens, and successful positive tokens. Migration, writer compatibility, authorization and P0 tests remain repository-owned.

Minimum CI is not browser E2E, own OCR evaluation, preview deployment, real device/screenreader testing, production migration rehearsal or distributed server safety. Independent review and verified absence of automatic production deployment remain mandatory merge gates.
