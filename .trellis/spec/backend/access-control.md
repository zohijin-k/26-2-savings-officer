# Access control for the savings backend

## 1. Scope / Trigger

Apply when adding or changing any route under `/api/applications/{id}`, `/api/files`
or `/api/officer`, the owner cookie set by `POST /api/applications`, the officer
login, middleware order in `demo/backend/main.py`, or a test that calls these
routes over HTTP. This backend serves the applicant frontend of
`26-2-savings-applicant` and this repository's officer frontend (see
[One backend for both frontends](./unified-backend.md)), so every applicant and
officer request crosses this boundary.

Ported from `26-2-youth` (`officer_auth.py`, `generic_access.py`, task
`11-18-access-control`). `officer_auth.py` is an unchanged copy. `applicant_access.py`
drops youth's generic programs, public blank assets, narrow-cookie migration and
per-application write lock.

## 2. Signatures

Backend:

- `demo/backend/officer_auth.py`
  - `router` (prefix `/api/officer`): `POST /login` body `{"password": str}` (max 4,096 chars), `GET /session`, `POST /logout`.
  - `configuration_error() -> str | None`, `session_expiry(request) -> int | None`, `is_officer(request) -> bool`.
  - `OfficerAccess` (ASGI middleware). Module state: `_failures`, `_revoked` (process memory).
  - Constants: `COOKIE_NAME = "officer_session"`, `SESSION_SECONDS = 28800`, `UNCONFIGURED`.
- `demo/backend/applicant_access.py`
  - `ApplicantAccess` (ASGI middleware), `DENIED = "신청자 본인만 접근할 수 있습니다."`.
- `demo/backend/main.py`: `add_middleware(ApplicantAccess)` then `add_middleware(OfficerAccess)`, both after `CORSMiddleware`; `include_router(officer_auth_router)`.
- `demo/backend/api/applications.py` `create`: cookie `applicant_access_{id}` with `path="/api"`.

Run command (repository root):

```bash
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

Test helpers (`demo/backend/tests/security_support.py`, identical to youth):

- `authenticate_officer(client, monkeypatch=None)` — sets synthetic `OFFICER_PASSWORD`/`OFFICER_SESSION_SECRET` and logs in through the real endpoint.
- `claim_synthetic_application(client, application_id)` — gives a DB-created synthetic application a fresh owner token and puts its cookie in the client.

## 3. Contracts

| Route | Who may call | Otherwise |
|---|---|---|
| `GET /api/health`, `GET /api/programs`, `GET /api/programs/{code}`, `GET /api/programs/{code}/criteria` | anyone | — |
| `POST /api/applications` | anyone; the response sets the owner cookie | — |
| every method under `/api/applications/{id}` (32 routes on 2026-11-19) | the owner cookie of that application | 403 `DENIED` |
| `GET /api/files/{document_id}` | the owner of the document's application, or a logged-in officer | 403 `DENIED` |
| every path equal to or under `/api/officer` (including future and unknown paths) | a logged-in officer; `POST /api/officer/login` is exempt | 401; 503 when unconfigured |

- Owner cookie: `applicant_access_{id}=<token_urlsafe(32)>; Path=/api; HttpOnly; SameSite=Lax; Max-Age=5 years`, `Secure` on https. Only `sha256(token)` is stored, in `Application.applicant_access_hash`. Comparison uses `hmac.compare_digest`.
- Officer cookie: `officer_session=<issued>.<expires>.<32 hex nonce>.<HMAC-SHA256>`; `Path=/api; HttpOnly; SameSite=Lax; Max-Age=28800`, `Secure` on https. Logout puts the token digest on the revocation list until it expires.
- Environment: `OFFICER_PASSWORD` and `OFFICER_SESSION_SECRET` are both required for any officer route, login included. The applicant routes do not read them.
- The route identifier is parsed with `TypeAdapter(int)`, the same lax integer conversion FastAPI applies to the path parameter. `+5`, `05`, `5.0`, ` 5` and `1_0` all name an application number, so the cookie is matched under the number the router will load.
- A missing, non-integer, non-positive or unknown number returns the same 403 as a wrong cookie. Responses never reveal whether an application or document exists.
- An officer session opens only `GET /api/files/*`. It never opens applicant reads or writes; the officer frontend does not call them.
- Rejections carry `Cache-Control: private, no-store`. `OPTIONS` requests pass through to CORS.
- Middleware order: the last `add_middleware` is outermost, so requests meet `OfficerAccess`, then `ApplicantAccess`, then CORS, then the routers. Guard responses therefore carry no CORS headers; both frontends call through their Vite proxy on the same origin.
- `api/forms.py` `_require_applicant_archive_access` still checks the written-forms PDF. It runs after the middleware and is kept so the applicant API files stay identical in both repositories.
- Officer login state is process memory: a server restart forgets failure counts and the revocation list, and one uvicorn worker is assumed. Changing `OFFICER_SESSION_SECRET` invalidates every session.

## 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| No cookie on `/api/applications/{id}/…` | 403 `{"detail": DENIED}` |
| Cookie of another application, or another owner's token under this name | 403 |
| Draft created before this access control (its cookie is scoped to `/api/applications/{id}/forms/files`) | 403 on every other route; start a new application in a new tab. No cookie migration (task decision D3) |
| DB-created application with `applicant_access_hash = NULL` and any cookie | 403; there is no credential recovery |
| Non-integer, zero, unknown application or document number | 403 |
| `GET /api/files/{id}` with a valid officer session | 200 inline original |
| `PATCH /api/applications/{id}` with only an officer session | 403 |
| An officer opens `forms[].file_url` from `GET /api/officer/applications/{id}` (`/api/applications/{id}/forms/{form_no}.pdf`) | 403. The officer frontend does not show these links; a future officer forms view needs an officer-readable route, not an applicant-route exception |
| `/api/officer/…` without a session, or with a forged, expired or logged-out token | 401 `담당자 로그인이 필요합니다.` |
| `Authorization: Bearer province` or `?role=province` without a session | 401; roles are screen scopes, not credentials |
| `OFFICER_PASSWORD` or `OFFICER_SESSION_SECRET` empty | 503 with the configuration message on every officer path, login included |
| Five wrong passwords from one client address | 429 with `Retry-After` for 60 seconds; a success resets the count |
| Backend started without `--env-file .env` | officer screen shows the 503 message; applicant screen works |

## 5. Good / Base / Bad Cases

- Good: the applicant creates an application, uploads and submits in the same browser; the officer logs in on 5174, opens the list, the detail and the original, and decides. Both cookies live in the same localhost cookie jar and each guard reads only its own.
- Base: `?mock=1` on the officer frontend renders the synthetic list with no login and no backend request.
- Bad: guarding only digit-shaped URLs (`/api/applications/+5` would skip the check while the router loads application 5).
- Bad: letting an officer session through applicant routes because the officer "should see everything"; the officer API already returns what the review screen needs.

## 6. Tests Required

- `tests/test_access_control.py` (59 cases on 2026-11-19) enumerates routes with `fastapi.routing.iter_route_contexts(app.routes)` (FastAPI 0.137.2+), which yields each included route with its served path. Since FastAPI 0.137 an included router stays a single `app.routes` entry, so looping over `app.routes` alone misses every route added with `include_router`. The enumeration guard fails when either list comes back short, so a FastAPI upgrade cannot silently drop the per-route cases:
  - every applicant route rejects no cookie, another application's cookie and another owner's token under the target name with 403, `DENIED` and `private, no-store`;
  - every officer route, `/api/officer` and an unknown officer path return 401 without a session and with a forged role header;
  - the owner cookie is `Path=/api`, HttpOnly, SameSite=Lax and `Secure` on https; private columns stay out of responses;
  - originals open for the owner and a logged-in officer only; the officer session cannot read, patch or delete applicant data;
  - tokenless legacy rows, integer aliases and unknown numbers stay closed, while the owner's cookie works under an alias;
  - login expiry, forgery, logout and replay; five-failure cooldown; unset password and unset secret give 503; https session cookie is `Secure`;
  - public routes need no credentials; one client may hold owner and officer cookies together.
- Existing tests and scenario modules call `authenticate_officer` or `claim_synthetic_application` before officer routes or DB-created applications. Expected responses are not changed; the list of touched files is in the task's `changed-tests.md`.
- Officer frontend: `tests/officer-session.test.ts` (see [Savings officer application views](../frontend/officer-documents.md)).

## 7. Wrong vs Correct

Wrong — a new test reads a DB-created application over HTTP without an owner:

```python
with models.get_session() as s:
    s.add(models.Application(application_no="X-1", program_code=DOUBLE_SAVINGS))
    s.commit()
client.get("/api/applications/1")          # 403
```

Correct:

```python
from demo.backend.tests.security_support import claim_synthetic_application
claim_synthetic_application(client, 1)
client.get("/api/applications/1")          # 200
```

Wrong — checking the officer role header as authentication:

```python
if request.headers.get("authorization") == "Bearer province": ...
```

Correct — `OfficerAccess` checks the signed `officer_session` cookie for the whole `/api/officer` namespace before any router runs; routers read the role only to choose the screen scope.
