"""Bulk revision values use the same HTTP 422 bounds as single decisions."""
import pytest
from sqlmodel import select
from demo.backend import models
from demo.backend.tests.test_review_revision import client, record
from demo.backend.tests.security_support import authenticate_officer
from demo.backend.review_revision import MAX_EXPECTED_REVISION

@pytest.fixture(autouse=True)
def authenticated(client, monkeypatch):
    authenticate_officer(client, monkeypatch)

@pytest.mark.parametrize("token", [0, -1, MAX_EXPECTED_REVISION + 1, 2**100, True, "1", 1.5, None])
def test_invalid_bulk_revision_is_422_and_preserves_entire_database(client, record, token):
    def state():
        with models.get_session() as session:
            return ([row.model_dump() for row in session.exec(select(models.Review))],
                    [row.model_dump() for row in session.exec(select(models.Application))])
    before = state()
    response = client.post("/api/officer/applications/decisions", json={
        "role": "province", "decision": "hold", "memo": "FAKE rejected bulk write",
        "application_ids": [record], "expected_revisions": {str(record): token},
    })
    assert response.status_code == 422
    assert state() == before
