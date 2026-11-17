# One backend for the applicant and officer frontends

## Scenario: applicant submissions appear in the officer database

### 1. Scope / Trigger

Apply when changing `demo/backend/api/applications.py`, `api/documents.py`,
`api/review.py`, the applicant projection in `api/common.py`, any test that
reads an applicant response, or the run instructions. This repository's backend
serves two frontends: the officer frontend in this repository and the applicant
frontend of `26-2-savings-applicant`. The contract crosses repositories, so
changes need this depth.

### 2. Signatures

Run topology (development):

```bash
uvicorn demo.backend.main:app --reload --port 8000        # this repository root
npm run dev                                               # ../26-2-savings-applicant/demo/frontend → 5173
npm run dev -- --port 5174                                # demo/frontend of this repository
```

API by audience:

- Applicant: `/api/applications…` (routers `applications`, `documents`, `forms`, `review`, `subsidy`) and `/api/programs/{code}/criteria`.
- Officer: `/api/officer…` and `/api/files/{document_id}`.

Functions:

- `api.common.REUPLOAD_CODES`, `api.common.applicant_findings(findings) -> list[dict]` — the applicant projection, see [Applicant submission](./applicant-submission.md).
- `api.common.document_fact(d) -> dict` — internal facts including the stored `findings`; never returned by an applicant endpoint.
- `demo.backend.tests.test_portal_uploads.assert_upload_status(data, expected)` — asserts the stored verdict and its public projection together.

### 3. Contracts

- One process and one database: this repository's `demo/demo.db` and `demo/storage/`. Nothing is copied between repositories.
- Both frontends' Vite proxies send `/api` to `http://localhost:8000`. No frontend code changes for the linked run.
- Applicant responses follow [Applicant submission](./applicant-submission.md): document `status` is `UPLOADED` or `REUPLOAD_REQUIRED`; findings are the allowlisted FAIL entries only; no `ocr_confidence`, eligibility blockers, self-check detail or threshold notes.
- Stored outcomes keep the engine's values: `Document.stage1_status`, `Document.findings_json` and `Review` rows follow [Confirmed failure filtering](./failure-filtering.md) and are never rewritten for the applicant projection.
- Officer responses do not use applicant projections. `api/officer.py` reads `checklist_for`, `list_documents`, `list_documents_bulk`, `load_application`, `subsidy_estimate` and `form_links`.
- A submitted application is visible to the officer immediately (`Application.status != draft`). An officer decision is stored in `Review` and shown by `GET /api/applications/{id}/status`.
- The applicant API code exists in both repositories with the same content: `api/applications.py`, `api/documents.py`, `api/review.py` and the applicant projection in `api/common.py`. A change in one repository must be applied to the other.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| The applicant repository's backend is started on 8000 instead of this one | submissions go to that repository's database and are assessed by its rules; nothing new appears on this officer screen |
| Both backends are started | the second cannot bind port 8000 |
| A test asserts an internal verdict through an applicant response `status` | fails, because applicant responses carry `UPLOADED` / `REUPLOAD_REQUIRED`; use `assert_upload_status` or read the stored row or the officer API |
| An applicant endpoint returns `document_fact` output or unfiltered stored findings | defect: internal judgment leaks to the applicant |
| A new FAIL code must make the applicant upload again | add it to `REUPLOAD_CODES` in both repositories with tests; otherwise the applicant sees `UPLOADED` and only the officer sees the FAIL |
| The applicant API is changed in one repository only | the linked run and the applicant repository's standalone run behave differently |

### 5. Good / Base / Bad Cases

- Good: an applicant uploads a low-quality but readable resident abstract. The stored finding is `LOW_IMAGE_QUALITY` with `NEEDS_REVIEW`, the applicant sees `UPLOADED` and can submit, and the officer list shows the application for checking.
- Base: only the officer frontend runs against this backend. Officer-only work is unchanged.
- Bad: restoring `"status": d.stage1_status` in `document_dict` to make an officer-side test pass.

### 6. Tests Required

- `tests/test_applicant_submission_policy.py`, `tests/test_applicant_supplement_projection.py`, `tests/test_applicant_failure_findings.py`: the applicant boundary.
- `tests/test_quality_assessment_parity.py`, `tests/test_payment_paging.py`, `tests/test_payment_paging_refinement.py`: stored verdicts through `assert_upload_status`, final-check blockers, submit status code and officer detail.
- `tests/test_officer_frontend_integration.py` and the officer API tests: officer responses unchanged.
- A screen check with both frontends on an isolated temporary database: submit, officer list and detail, officer decision, applicant my page. Synthetic documents only.

### 7. Wrong vs Correct

Wrong:

```python
response = client.post(f"/api/applications/{aid}/documents", ...).json()
assert response["status"] == "FAIL"
```

Correct:

```python
assert_upload_status(response, "FAIL")   # stored stage1_status plus the public projection
```

Wrong: starting the applicant repository's backend to demonstrate the linked flow.

Correct: start this repository's backend on port 8000 and attach both frontends.
