"""Synthetic owner-cookie and officer-login boundary checks.

Routes are enumerated from the running app, so an applicant or officer route
added later is checked without editing this file. See
`.trellis/spec/backend/access-control.md`.
"""
import re

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from demo.backend import models, officer_auth
from demo.backend.api import applications, common, documents, files, forms
from demo.backend.applicant_access import DENIED
from demo.backend.main import app
from demo.backend.rules.programs import DOUBLE_SAVINGS

PASSWORD = "synthetic-officer-password"
PRIVATE_COLUMNS = {"applicant_access_hash", "written_forms_archive_path", "written_forms_archive_count"}
_PLACEHOLDER = re.compile(r"\{(\w+)(?::\w+)?\}")
_SAMPLE_VALUES = {"document_id": "1", "form_no": "서식1", "page_no": "1", "code": DOUBLE_SAVINGS}


def _routes(prefix):
    found = []
    # FastAPI 0.162.2 keeps included routers grouped; contexts expose their effective paths.
    for route in iter_route_contexts(app.routes):
        if isinstance(route.original_route, APIRoute) and (route.path == prefix or route.path.startswith(prefix + "/")):
            found.extend((method, route.path) for method in sorted(route.methods))
    return found


APPLICANT_ROUTES = _routes("/api/applications/{application_id}")
OFFICER_ROUTES = [route for route in _routes("/api/officer") if route != ("POST", "/api/officer/login")]


def _fill(template, application_id):
    values = {**_SAMPLE_VALUES, "application_id": str(application_id)}
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)


@pytest.fixture
def security(tmp_path, monkeypatch):
    isolated = create_engine(f"sqlite:///{tmp_path / 'synthetic-access.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(models, "engine", isolated)
    storage = tmp_path / "storage"
    for module in (applications, common, documents, files, forms):
        monkeypatch.setattr(module, "STORAGE", storage)
    monkeypatch.setattr(applications, "SIGNATURES", storage / "signatures")
    monkeypatch.setattr(documents, "DOCUMENTS", storage / "documents")
    monkeypatch.setenv("OFFICER_PASSWORD", PASSWORD)
    monkeypatch.setenv("OFFICER_SESSION_SECRET", "synthetic-session-key-for-access-tests")
    monkeypatch.setenv("ENGINE_V2_OCR", "off")
    officer_auth._failures.clear()
    officer_auth._revoked.clear()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        officer_auth._failures.clear()
        officer_auth._revoked.clear()
        isolated.dispose()


def new_application(client):
    response = client.post("/api/applications", json={"program_code": DOUBLE_SAVINGS})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def login(client):
    return client.post("/api/officer/login", json={"password": PASSWORD})


def synthetic_original(application_id):
    payload = b"%PDF-1.4\n% synthetic original\n"
    root = common.STORAGE
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"synthetic-{application_id}.pdf"
    target.write_bytes(payload)
    with models.get_session() as session:
        document = models.Document(application_id=application_id, slot_key="synthetic",
                                   file_path=str(target.relative_to(root.parent)), file_format="pdf")
        session.add(document)
        session.commit()
        session.refresh(document)
        return document.id, payload


def test_route_enumeration_covers_the_current_api():
    # 32 applicant routes beneath an application number; 9 officer routes plus session and logout.
    assert len(APPLICANT_ROUTES) >= 32
    assert len(OFFICER_ROUTES) >= 11
    assert ("GET", "/api/officer/session") in OFFICER_ROUTES and ("POST", "/api/officer/logout") in OFFICER_ROUTES


@pytest.mark.parametrize("method,template", APPLICANT_ROUTES)
def test_every_applicant_route_rejects_missing_and_other_owner(security, method, template):
    target = new_application(security)
    path = _fill(template, target)
    outsider = TestClient(app)
    other = new_application(outsider)
    other_token = outsider.cookies.get(f"applicant_access_{other}")
    # No cookie, another application's own cookie, and another owner's token under this name.
    for cookies in ({}, {f"applicant_access_{other}": other_token}, {f"applicant_access_{target}": other_token}):
        stranger = TestClient(app)
        for name, value in cookies.items():
            stranger.cookies.set(name, value, path="/api")
        result = stranger.request(method, path, json={})
        assert result.status_code == 403, (method, template, cookies.keys(), result.text)
        assert result.json() == {"detail": DENIED}
        assert result.headers["cache-control"] == "private, no-store"
    assert security.get(f"/api/applications/{target}").status_code == 200


@pytest.mark.parametrize("base_url,secure", [("http://testserver", False), ("https://testserver", True)])
def test_owner_cookie_covers_the_whole_api_and_hides_private_columns(security, base_url, secure):
    owner = TestClient(app, base_url=base_url)
    created = owner.post("/api/applications", json={"program_code": DOUBLE_SAVINGS})
    header = created.headers["set-cookie"]
    assert "Path=/api;" in header and "HttpOnly" in header and "SameSite=lax" in header
    assert ("Secure" in header) == secure
    identifier = created.json()["id"]
    response = owner.patch(f"/api/applications/{identifier}", json={"form1": {"name": "합성신청"}})
    assert response.status_code == 200
    assert not PRIVATE_COLUMNS & response.json().keys()
    document_id, payload = synthetic_original(identifier)
    original = owner.get(f"/api/files/{document_id}")
    assert original.status_code == 200 and original.content == payload


def test_originals_open_for_owner_and_logged_in_officer_only(security):
    identifier = new_application(security)
    document_id, payload = synthetic_original(identifier)
    original = security.get(f"/api/files/{document_id}")
    assert original.status_code == 200 and original.content == payload
    assert original.headers["content-disposition"].startswith("inline")
    officer = TestClient(app)
    assert officer.get(f"/api/files/{document_id}").status_code == 403
    assert officer.get("/api/files/9999999").status_code == 403
    assert login(officer).status_code == 200
    viewed = officer.get(f"/api/files/{document_id}")
    assert viewed.status_code == 200 and viewed.content == payload
    # An officer session views originals only; applicant data and changes stay closed.
    assert officer.get(f"/api/applications/{identifier}").status_code == 403
    assert officer.get(f"/api/applications/{identifier}/documents").status_code == 403
    assert officer.patch(f"/api/applications/{identifier}", json={"form1": {}}).status_code == 403
    assert officer.delete(f"/api/applications/{identifier}/documents/{document_id}").status_code == 403


def test_tokenless_application_unknown_numbers_and_integer_aliases_stay_closed(security):
    with models.get_session() as session:
        row = models.Application(application_no="SYNTHETIC-LEGACY", program_code=DOUBLE_SAVINGS)
        session.add(row)
        session.commit()
        session.refresh(row)
        legacy = row.id
    for alias in (str(legacy), f"+{legacy}", f"0{legacy}", f"{legacy}.0"):
        assert security.get(f"/api/applications/{alias}").status_code == 403
    # A client-chosen cookie cannot mint a credential for an application without a stored token.
    security.cookies.set(f"applicant_access_{legacy}", "synthetic-forged", path="/api")
    assert security.get(f"/api/applications/{legacy}").status_code == 403
    owned = new_application(security)
    stranger = TestClient(app)
    for alias in (f"+{owned}", f"0{owned}", f"{owned}.0"):
        assert stranger.get(f"/api/applications/{alias}").status_code == 403
        # The owner's cookie is matched under the same number the router would use.
        assert security.get(f"/api/applications/{alias}").status_code != 403
    for path in ("/api/applications/abc", "/api/applications/0", "/api/applications/9999999",
                 "/api/applications/", "/api/files/abc", "/api/files/0"):
        assert stranger.get(path).status_code == 403, path


@pytest.mark.parametrize("method,template", OFFICER_ROUTES + [("GET", "/api/officer"), ("GET", "/api/officer/unknown")])
def test_every_officer_route_requires_a_session(security, method, template):
    path = _fill(template, 1)
    assert security.request(method, path, json={}).status_code == 401
    # Role names select a screen scope after login; they are never credentials.
    forged = security.request(method, f"{path}?role=province", json={}, headers={"Authorization": "Bearer province"})
    assert forged.status_code == 401


def test_login_expiry_forgery_logout_and_replay(security, monkeypatch):
    result = login(security)
    assert result.status_code == 200
    header = result.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/api" in header and "Max-Age=28800" in header
    assert security.get("/api/officer/session").status_code == 200
    assert security.get("/api/officer/applications").status_code == 200
    token = security.cookies.get("officer_session")
    stranger = TestClient(app)
    stranger.cookies.set("officer_session", token[:-1] + ("a" if token[-1] != "a" else "b"), path="/api")
    assert stranger.get("/api/officer/session").status_code == 401
    real_time = officer_auth.time.time
    monkeypatch.setattr(officer_auth.time, "time", lambda: real_time() + 28801)
    assert security.get("/api/officer/session").status_code == 401
    monkeypatch.setattr(officer_auth.time, "time", real_time)
    assert security.post("/api/officer/logout").status_code == 200
    assert security.get("/api/officer/session").status_code == 401
    stranger.cookies.set("officer_session", token, path="/api")
    assert stranger.get("/api/officer/session").status_code == 401


def test_five_login_failures_enforce_cooldown_and_success_resets_count(security, monkeypatch):
    for _ in range(4):
        assert security.post("/api/officer/login", json={"password": "wrong"}).status_code == 401
    assert login(security).status_code == 200
    security.cookies.clear()
    for _ in range(5):
        assert security.post("/api/officer/login", json={"password": "wrong"}).status_code == 401
    blocked = login(security)
    assert blocked.status_code == 429 and 1 <= int(blocked.headers["retry-after"]) <= 60
    real_time = officer_auth.time.time
    monkeypatch.setattr(officer_auth.time, "time", lambda: real_time() + 61)
    assert login(security).status_code == 200


@pytest.mark.parametrize("path,method", [
    ("/api/officer/login", "POST"), ("/api/officer/session", "GET"),
    ("/api/officer/applications", "GET"), ("/api/officer/logout", "POST"),
])
def test_unset_password_disables_the_whole_officer_namespace(security, monkeypatch, path, method):
    assert login(security).status_code == 200
    monkeypatch.setenv("OFFICER_PASSWORD", "")
    response = security.request(method, path, json={"password": "anything"})
    assert response.status_code == 503
    assert response.json()["detail"] == officer_auth.UNCONFIGURED


def test_unset_secret_and_https_session_cookie(security, monkeypatch):
    secure = TestClient(app, base_url="https://testserver")
    assert "Secure" in login(secure).headers["set-cookie"]
    monkeypatch.setenv("OFFICER_SESSION_SECRET", "")
    assert login(security).status_code == 503


def test_public_routes_need_no_credentials(security):
    stranger = TestClient(app)
    for path in ("/api/health", "/api/programs", f"/api/programs/{DOUBLE_SAVINGS}",
                 f"/api/programs/{DOUBLE_SAVINGS}/criteria"):
        assert stranger.get(path).status_code == 200, path
    assert stranger.post("/api/applications", json={"program_code": DOUBLE_SAVINGS}).status_code == 200


def test_one_browser_may_hold_owner_and_officer_cookies(security):
    # Linked run: both frontends share localhost cookies; each guard reads only its own cookie.
    identifier = new_application(security)
    assert login(security).status_code == 200
    assert security.get(f"/api/applications/{identifier}").status_code == 200
    assert security.get("/api/officer/applications").status_code == 200
    assert security.post("/api/officer/logout").status_code == 200
    assert security.get(f"/api/applications/{identifier}").status_code == 200
    assert security.get("/api/officer/applications").status_code == 401
