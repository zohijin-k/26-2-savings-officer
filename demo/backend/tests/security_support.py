"""Explicit synthetic credentials for existing authenticated API scenarios."""
from __future__ import annotations

import os
import hashlib
import secrets
from typing import Any


def authenticate_officer(client: Any, monkeypatch: Any = None) -> None:
    """Log in through the production endpoint using test-only environment values.

    Pytest fixtures pass their monkeypatch so environment changes are restored.
    Standalone scenario modules run in their own process and keep these values
    for the lifetime of their synthetic server.
    """
    values = {
        "OFFICER_PASSWORD": "synthetic-officer-password",
        "OFFICER_SESSION_SECRET": "synthetic-officer-session-secret-for-tests",
    }
    for key, value in values.items():
        if monkeypatch is None:
            os.environ[key] = value
        else:
            monkeypatch.setenv(key, value)
    response = client.post("/api/officer/login", json={"password": values["OFFICER_PASSWORD"]})
    assert response.status_code == 200, "Synthetic officer login failed"


def claim_synthetic_application(client: Any, application_id: int) -> None:
    """Give an explicitly DB-seeded synthetic actor its own owner credential."""
    from demo.backend import models

    token = secrets.token_urlsafe(32)
    with models.get_session() as session:
        application = session.get(models.Application, application_id)
        assert application is not None, "Synthetic application is missing"
        application.applicant_access_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        session.add(application)
        session.commit()
    client.cookies.set(f'applicant_access_{application_id}', token, path='/api')
