"""Unsupported auto uploads never touch synthetic persistent state or assessment."""
from copy import deepcopy
from datetime import datetime
import hashlib
from unittest.mock import AsyncMock, Mock

import pymupdf
import pytest
from starlette.formparsers import MultiPartParser
from sqlmodel import select

from demo.backend import models
from demo.backend.api import documents, review
from demo.backend.tests.security_support import authenticate_officer, claim_synthetic_application
from demo.backend.tests.test_eligibility_blockers import ready
from demo.backend.tests.test_income_review import make_application
from demo.backend.tests.test_portal_uploads import client
from engine_v2.tests.nhis_form_samples import acquisition_cells, text_pdf
from engine_v2.tests.test_insurance_workplace_consistency import NAME, OTHER, synthetic_cells

AUTO_DETAIL = (
    "자동 서류 분류 업로드는 현재 지원하지 않습니다. "
    "서류 종류에 맞는 업로드 항목을 선택해 다시 제출해 주세요."
)


def _database_snapshot():
    """Include all applications, documents, reviews, summaries, consents and criteria."""
    with models.engine.connect() as connection:
        return {
            table.name: deepcopy([
                dict(row) for row in connection.execute(
                    table.select().order_by(*table.primary_key.columns)
                ).mappings()
            ])
            for table in models.SQLModel.metadata.sorted_tables
        }


def _file_snapshot():
    return {
        str(path.relative_to(documents.STORAGE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in documents.STORAGE.rglob("*") if path.is_file()
    }


def _queue(client):
    response = client.get("/api/officer/applications", params={"ai_status": "PASS"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def prepared(client, tmp_path, monkeypatch):
    application = ready(make_application(premium=1))
    claim_synthetic_application(client, application.id)
    stored_review = review._run_review(application)
    assert stored_review.final_status == "PASS"
    with models.get_session() as session:
        stored = session.get(models.Application, application.id)
        stored.status = models.STATUS_SUBMITTED
        stored.submitted_at = datetime(2026, 6, 1, 12)
        session.add(stored)
        session.add(stored_review)
        session.commit()
    # A second existing application and stored original must also stay untouched.
    assert client.post("/api/applications", json={"program_code": application.program_code}).status_code == 200
    existing = documents.DOCUMENTS / application.application_no / "resident_abstract" / "FAKE-existing.pdf"
    existing.parent.mkdir(parents=True)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((30, 30), "SYNTHETIC EXISTING ORIGINAL")
        pdf.save(existing)
    authenticate_officer(client, monkeypatch)
    queue = _queue(client)
    assert queue["total"] == 1
    assert queue["rows"][0]["application_id"] == application.id
    return application.id


@pytest.fixture
def no_processing(monkeypatch):
    calls = {}
    for name in ("read_document", "assess_upload", "check_document", "split_pdf_pages",
                 "_save_row", "_replace_existing", "_refresh_nhis_identity"):
        spy = Mock(side_effect=AssertionError(f"Rejected upload called {name}"))
        monkeypatch.setattr(documents, name, spy)
        calls[name] = spy
    merged = AsyncMock(side_effect=AssertionError("Rejected upload reached merged helper"))
    monkeypatch.setattr(documents, "_upload_merged", merged)
    calls["merged"] = merged
    run_review = Mock(side_effect=AssertionError("Rejected upload recalculated review"))
    monkeypatch.setattr(review, "_run_review", run_review)
    calls["review"] = run_review
    return calls


def _assert_rejected_unchanged(client, aid, payload, no_processing, *, data=None, query="", detail=AUTO_DETAIL):
    queue_before = _queue(client)
    database_before, files_before = _database_snapshot(), _file_snapshot()
    response = client.post(
        f"/api/applications/{aid}/documents{query}",
        files={"file": ("FAKE-input.pdf", payload, "application/pdf")},
        data=data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert _database_snapshot() == database_before
    assert _file_snapshot() == files_before
    assert _queue(client) == queue_before
    assert _database_snapshot() == database_before
    for spy in no_processing.values():
        spy.assert_not_called()


@pytest.fixture
def pdf_payload(request, tmp_path):
    kind = request.param
    path = tmp_path / "FAKE-input.pdf"
    if kind == "workplace-conflict":
        text_pdf(path, synthetic_cells("portal", [NAME, OTHER, NAME, NAME]))
    else:
        cells = acquisition_cells(name="가상다른인" if kind == "identity-mismatch" else "가상신청")
        text_pdf(path, cells)
    if kind == "image":
        with pymupdf.open(path) as source, pymupdf.open() as raster:
            page = raster.new_page(width=595, height=842)
            page.insert_image(page.rect, pixmap=source[0].get_pixmap(dpi=100))
            payload = raster.tobytes()
        with pymupdf.open(stream=payload, filetype="pdf") as pdf:
            assert not pdf[0].get_text().strip()
        return payload
    with pymupdf.open(path) as pdf:
        assert pdf[0].get_text().strip()
    return path.read_bytes()


@pytest.mark.parametrize("pdf_payload", ["image", "text", "identity-mismatch", "workplace-conflict"], indirect=True)
def test_auto_pdf_content_is_rejected_before_processing_and_without_side_effects(
    client, prepared, pdf_payload, no_processing,
):
    _assert_rejected_unchanged(client, prepared, pdf_payload, no_processing, data={"slot_key": "auto"})


@pytest.mark.parametrize("data,query", [
    (None, ""),
    ({"slot_key": ""}, ""),
    ({"slot_key": None}, ""),
    (None, "?slot_key=resident_abstract"),
    ({"slot_key": ""}, "?slot_key=resident_abstract"),
    ({"slot_key": "auto"}, "?slot_key=resident_abstract"),
], ids=["omitted", "empty", "multipart-null-as-empty", "query-cannot-supply-form", "empty-with-query", "auto-with-query"])
def test_implicit_auto_forms_are_rejected_without_side_effects(client, prepared, no_processing, data, query):
    _assert_rejected_unchanged(client, prepared, b"%PDF-1.4\n%SYNTHETIC", no_processing, data=data, query=query)


@pytest.mark.parametrize("slot", [" ", "\t", "null", "None", "AUTO", " auto ", "unassigned", "FAKE-unknown"])
def test_other_unsupported_slots_keep_explicit_400_and_no_side_effects(client, prepared, no_processing, slot):
    _assert_rejected_unchanged(
        client, prepared, b"%PDF-1.4\n%SYNTHETIC", no_processing,
        data={"slot_key": slot}, detail=f"업로드 대상이 아닌 슬롯입니다: {slot}",
    )


@pytest.mark.parametrize("existing_status", ["FAIL", "NEEDS_REVIEW"])
def test_rejected_auto_cannot_weaken_existing_document_or_review(client, prepared, no_processing, existing_status):
    with models.get_session() as session:
        doc = session.exec(select(models.Document).where(models.Document.application_id == prepared)).first()
        doc.stage1_status = existing_status
        doc.findings_json = [{"code": "IDENTITY_MISMATCH", "severity": existing_status, "message": "합성 본인 대조"}]
        current = session.exec(select(models.Review).where(models.Review.application_id == prepared)).one()
        current.final_status = existing_status
        session.add(doc)
        session.add(current)
        session.commit()
    _assert_rejected_unchanged(client, prepared, b"%PDF-1.4\n%SYNTHETIC", no_processing, data={"slot_key": "auto"})


@pytest.mark.parametrize("rolled", [False, True], ids=["memory", "rolled-storage"])
def test_rejected_multipart_upload_is_closed_by_framework(client, prepared, no_processing, monkeypatch, rolled):
    import starlette.formparsers as formparsers

    # Keep the test small while exercising the actual on-disk rollover path.
    monkeypatch.setattr(MultiPartParser, "spool_max_size", 32 if rolled else 1024)
    original = formparsers.SpooledTemporaryFile
    handles = []

    def capture(*args, **kwargs):
        handle = original(*args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", capture)
    _assert_rejected_unchanged(client, prepared, b"%PDF-1.4\n" + b"SYNTHETIC" * 20, no_processing,
                               data={"slot_key": "auto"})
    assert len(handles) == 1
    assert handles[0]._rolled is rolled
    assert handles[0].closed


def test_historical_unassigned_document_can_keep_pass_and_is_not_automatically_reassessed(client, prepared):
    with models.get_session() as session:
        row = models.Document(
            application_id=prepared, slot_key=models.UNASSIGNED_SLOT,
            file_path="FAKE-unassigned.pdf", file_format="pdf", stage1_status="NEEDS_REVIEW",
            findings_json=[], ocr_json={"confidence": 0, "fields": {}},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        unassigned_id = row.id
    # Ordinary reads neither upgrade the legacy row nor invalidate the old PASS.
    before = _database_snapshot()
    assert client.get(f"/api/applications/{prepared}/documents").status_code == 200
    assert client.get(f"/api/applications/{prepared}/status").status_code == 200
    assert _queue(client)["total"] == 1
    assert _database_snapshot() == before
    with models.get_session() as session:
        application = session.get(models.Application, prepared)
    # Even an explicit fresh review ignores old unassigned rows. This is a
    # documented residual risk, not a desired contract fixed by this boundary.
    assert review._run_review(application).final_status == "PASS"
    with models.get_session() as session:
        assert session.get(models.Document, unassigned_id).stage1_status == "NEEDS_REVIEW"
