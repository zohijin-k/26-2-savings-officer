# Synthetic Review safety CI

PRODUCTION_NOT_READY. No deployment, production database, production secrets, external OCR/LLM, or real documents.

This independent CI PR targets main and does not modify CAS PR #37 (901690fe685c7b050d3d8a6405dbcd6a68c797be).
The event lane tests the exact event HEAD. The phase6d-cas lane tests the fixed CAS HEAD above; a missing CAS regression file fails closed. Both lanes print the actual source SHA and run critical repository-owned backend tests plus types/build/lint/all discovered Node tests.

CI PR checks belong to the CI PR and do **not** populate the CAS PR's required check contexts. Never manufacture a CAS status or bypass rules. Review and merge this CI PR separately through normal protection/review gates (this task does not authorize merging other PRs); after it reaches main, refresh/rerun the CAS PR through an authorized integration step and verify the actual checked SHA/context before merging CAS. Passing the fixed-head lane is related SHA-specific CI evidence only.

The pinned Phase 6D lane must be retired/updated during Phase 6E after both CAS and CI integration. Phase 6E must add preview E2E, browser/accessibility, complete suites, dependency locks and mature secret/dependency scanning. The value-free signature/path scanner here is a minimum gate, not comprehensive secret/PII or vulnerability certification.

Backend installs use repository requirements plus explicit test/numeric dependencies from PyPI. Frontend uses npm ci, lock integrity and registry.npmjs.org, without lifecycle scripts. Python test sockets and non-synthetic SQLite are blocked, including spawned workers. Tests generate temporary synthetic fixtures only. Hosted logs contain no production secrets by design; do not attach DB/PDF/cookies.

Actions use verified full commit SHAs, contents read, no persisted git credentials, no privileged PR trigger, no deployment command, no environment binding. Default repo permissions/protection are not changed by this PR.
