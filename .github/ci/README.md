# Synthetic Review safety CI

PRODUCTION_NOT_READY. No deployment, environment binding, production DB, secrets or real documents. External OCR/LLM is disabled. Python tests block network and SQLite outside the synthetic root. Official Actions use full SHA pins, contents read permission, persist-credentials false and disabled npm lifecycle scripts. Transitive Python dependency hash locking and mature dependency scans remain future work.

Six jobs retain three source lanes with backend and frontend checks:

- `event`: the exact event merge ref (`github.sha`) or push SHA.
- `pr-head`: the exact event PR HEAD. For the designated CI-only PR, resolve the current `feat/phase6d-review-cas` remote HEAD to an immutable SHA before checkout instead.
- `latest-main`: latest fetched main plus that same immutable subject HEAD, resolved with `git merge-tree --write-tree`. No synthetic merge commit is created. A merge conflict fails the job.

`SOURCE_PROVENANCE` and the step summary distinguish event PR HEAD/base/merge, subject HEAD/branch, latest main, tested commit/tree, integration parents, check owner SHA and Actions run/attempt. CI-only PR results remain attached to the CI PR. They do not replace the CAS PR's own checks. The CAS PR must contain this workflow and receive its own pull_request event. No workflow_dispatch or pull_request_target is used.

CAS PR lanes and CI PR candidate lanes fail closed if required CAS or bulk 422 regression tests are absent. A CAS implementation detected in any source also requires its bulk correction. Tests preserve 428 missing preconditions, 422 strict types/ranges, 409 stale valid tokens, positive-token success, full DB invariance, migration, writer compatibility, authorization, P0 and Privacy.

The workflow runs on pull requests targeting main or the CAS feature branch and pushes to main. There are no path filters or deployment steps. No branch protection or required checks are changed. Zero teammate approvals is not a self-imposed gate; actual GitHub review requirements apply.

This minimum CI does not replace full synthetic browser E2E, own OCR evaluation, device/screenreader checks, production migration rehearsal or deployment safety investigation. Main merge requires resolved production auto-deploy risk and all requested release gates. Never infer no external deployment from empty GitHub deployment history.

CAS subjects must include mixed-writer SQLite guard and integrity-closure regressions. The backend lane fails closed if either required module is missing; integrity tests cover cross-application review preservation and DELETE/REPLACE ABA. Production migration and deployment are outside this workflow.
