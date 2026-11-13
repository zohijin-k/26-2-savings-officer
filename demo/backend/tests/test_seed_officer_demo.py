"""Synthetic-only acceptance for persistent officer demo seeding."""
import hashlib
import json
from pathlib import Path

import pytest
from sqlmodel import create_engine, select

from demo.backend import models
from demo.backend.api import applications, common, documents, files, forms, officer
from demo.backend.tools import seed_officer_demo as tool


@pytest.fixture
def isolated_demo(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    root.mkdir()
    storage = root / "storage"
    storage.mkdir()
    database = create_engine(f"sqlite:///{root / 'demo.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(tool, "DEMO_ROOT", root)
    monkeypatch.setattr(models, "DB_PATH", root / "demo.db")
    monkeypatch.setattr(models, "engine", database)
    for module in (applications, common, documents, files, forms):
        monkeypatch.setattr(module, "STORAGE", storage)
    monkeypatch.setattr(applications, "SIGNATURES", storage / "signatures")
    monkeypatch.setattr(documents, "DOCUMENTS", storage / "documents")
    models.init_db()
    yield root
    database.dispose()


def payload(capsys):
    return json.loads(capsys.readouterr().out)


def stored_files(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / "storage").rglob("*") if path.is_file()}


def unrelated(root):
    path = root / "storage" / "FAKE-unrelated.pdf"
    path.write_bytes(b"FAKE-unrelated-document")
    with models.get_session() as session:
        app = models.Application(application_no="FAKE-UNRELATED", program_code="double_savings",
                                 status="submitted", form1_json={"name": "가상기존"})
        session.add(app)
        session.commit()
        session.refresh(app)
        session.add(models.Document(application_id=app.id, slot_key="resident_abstract", file_format="pdf",
                                    file_path="storage/FAKE-unrelated.pdf", stage1_status="FAIL",
                                    findings_json=[{"code": "FAKE_EXISTING", "message": "합성 기존 사유"}]))
        session.add(models.Review(application_id=app.id, stage1_status="FAIL", final_status="FAIL",
                                  review_payload_json={"reasons": [{"code": "FAKE_OLD"}]}))
        session.commit()
        aid = app.id
    return aid


def test_creates_two_submitted_synthetic_examples_and_original_files(isolated_demo, capsys):
    assert tool.main([]) == 0
    result = payload(capsys)
    assert result["created"] == 2 and result["existing"] == 0
    assert result["applications"]["pass"]["pass"] == 5
    assert result["applications"]["pass"]["needs_review"] == 0
    assert result["applications"]["needs-review"]["needs_review"] >= 1
    listing = officer.list_applications(role="province", program="double_savings", status=None, ai_status=None, sort=None)
    assert listing["total"] == 2
    ids = {scenario: item["application_id"] for scenario, item in result["applications"].items()}
    normal = next(row for row in listing["rows"] if row["application_id"] == ids["pass"])
    review = next(row for row in listing["rows"] if row["application_id"] == ids["needs-review"])
    assert normal["documents"] and all(item["status"] == "PASS" for item in normal["documents"])
    assert any(item["status"] != "PASS" for item in review["documents"])
    for aid in ids.values():
        detail = officer.review_detail(aid, role="province")
        assert detail["documents"] and detail["forms"]
        assert (isolated_demo / common.load_application(aid).written_forms_archive_path).is_file()
        for document in detail["documents"]:
            response = files.stream_document(document["document_id"])
            assert response.media_type == "application/pdf"
            assert "inline" in response.headers["content-disposition"]
            assert Path(response.path).is_file()
    assert any(document["findings"] for document in officer.review_detail(ids["needs-review"], role="province")["documents"]
               if document["status"] != "PASS")


def test_repeat_does_not_change_existing_rows_or_files(isolated_demo, capsys):
    unrelated(isolated_demo)
    assert tool.main([]) == 0
    first = payload(capsys)
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    assert tool.main([]) == 0
    second = payload(capsys)
    assert second["created"] == 0 and second["existing"] == 2
    assert second["applications"] == first["applications"]
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before


def test_clean_removes_only_owned_rows_and_files_and_is_repeatable(isolated_demo, capsys):
    other_id = unrelated(isolated_demo)
    before = tool._snapshot()
    files_before = stored_files(isolated_demo)
    assert tool.main([]) == 0
    payload(capsys)
    assert all(tool._snapshot().get(key) == value for key, value in before.items())
    assert tool.main(["--clean"]) == 0
    result = payload(capsys)
    assert result["deleted_applications"] == 2 and result["deleted_files"] == 14
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before
    assert common.load_application(other_id).status == "submitted"
    assert tool.main(["--clean"]) == 0
    assert payload(capsys) == {"deleted_applications": 0, "deleted_rows": 0, "deleted_files": 0}
    assert tool.main([]) == 0
    assert payload(capsys)["created"] == 2


def test_clean_preserves_shared_and_unrelated_storage_files(isolated_demo, capsys):
    aid = unrelated(isolated_demo)
    assert tool.main([]) == 0
    result = payload(capsys)
    owned_id = result["applications"]["pass"]["application_id"]
    with models.get_session() as session:
        owned = session.exec(select(models.Document).where(models.Document.application_id == owned_id)).first()
        shared = isolated_demo / owned.file_path
        session.add(models.Document(application_id=aid, slot_key="FAKE-shared", file_format="pdf", file_path=owned.file_path))
        session.commit()
    original = shared.read_bytes()
    extra = isolated_demo / "storage" / "signatures" / "FAKE-untouched.png"
    extra.write_bytes(b"FAKE-unrelated-signature")
    assert tool.main(["--clean"]) == 0
    payload(capsys)
    assert shared.read_bytes() == original and extra.read_bytes() == b"FAKE-unrelated-signature"


def test_creation_failure_rolls_back_new_rows_and_files(isolated_demo, capsys, monkeypatch):
    unrelated(isolated_demo)
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    real_create = tool._create
    def fail_second(scenario, *args):
        if scenario == "needs-review":
            raise RuntimeError("FAKE-suppressed-error")
        return real_create(scenario, *args)
    monkeypatch.setattr(tool, "_create", fail_second)
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: SEED_ERROR\n"
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before


def test_clean_failure_restores_rows_and_files(isolated_demo, capsys, monkeypatch):
    assert tool.main([]) == 0
    payload(capsys)
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    original = models.Session.delete
    def fail_delete(self, instance):
        if isinstance(instance, models.Application):
            raise RuntimeError("FAKE-clean-failure")
        return original(self, instance)
    monkeypatch.setattr(models.Session, "delete", fail_delete)
    assert tool.main(["--clean"]) == 2
    assert capsys.readouterr().out == "error: SEED_ERROR\n"
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before


@pytest.mark.parametrize("arguments", [["some.pdf"], ["--db", "other.db"], ["--samples", "elsewhere"],
                                        ["--program", "job_package"], ["--application-id", "1"]])
def test_no_input_path_or_target_override(arguments, isolated_demo, capsys):
    before = tool._snapshot()
    assert tool.main(arguments) == 2
    assert capsys.readouterr().out == "error: ARGUMENT_ERROR\n"
    assert tool._snapshot() == before


def test_wrong_database_is_refused_before_access(isolated_demo, monkeypatch, capsys):
    outsider = isolated_demo.parent / "FAKE-other.db"
    database = create_engine(f"sqlite:///{outsider}")
    monkeypatch.setattr(models, "engine", database)
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: DEMO_DB_REQUIRED\n"
    assert not outsider.exists()
    database.dispose()


def test_symlink_database_refused(isolated_demo, monkeypatch, capsys):
    original = isolated_demo / "demo.db"
    moved = isolated_demo / "FAKE-moved.db"
    original.rename(moved)
    original.symlink_to(moved)
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: DEMO_DB_REQUIRED\n"


@pytest.mark.parametrize("part", ["storage", "storage/documents", "storage/signatures", "storage/forms_exports"])
def test_symlink_storage_refused(part, isolated_demo, capsys):
    path = isolated_demo / part
    if path.exists():
        path.rmdir()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    target = isolated_demo.parent / "FAKE-outside"
    target.mkdir()
    path.symlink_to(target, target_is_directory=True)
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: STORAGE_UNSAFE\n"
    assert not any(target.iterdir())


def test_missing_synthetic_sample_refuses_before_db_changes(isolated_demo, capsys, monkeypatch):
    before = tool._snapshot()
    monkeypatch.setattr(tool, "SAMPLES", isolated_demo / "FAKE-missing-samples")
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: SYNTHETIC_SAMPLES_REQUIRED\n"
    assert tool._snapshot() == before


def test_duplicate_marker_refuses_without_mutation(isolated_demo, capsys):
    for number in range(2):
        with models.get_session() as session:
            session.add(models.Application(application_no=f"FAKE-DUP-{number}", program_code="double_savings",
                                           form1_json={tool.MARKER_KEY: tool._marker("pass")}))
            session.commit()
    before = tool._snapshot()
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: DUPLICATE_MARKER\n"
    assert tool._snapshot() == before


def test_submission_side_effect_on_existing_data_is_rolled_back(isolated_demo, capsys, monkeypatch):
    from demo.backend.api import review
    aid = unrelated(isolated_demo)
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    original_submit = review.submit
    def alter_existing(application_id):
        result = original_submit(application_id)
        with models.get_session() as session:
            saved = session.get(models.Application, aid)
            saved.status = "reviewing"
            session.add(saved)
            session.commit()
        return result
    monkeypatch.setattr(review, "submit", alter_existing)
    assert tool.main([]) == 2
    assert capsys.readouterr().out == "error: EXISTING_DATA_CHANGED\n"
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before


def test_clean_rejects_owned_path_referencing_unrelated_storage(isolated_demo, capsys):
    unrelated(isolated_demo)
    assert tool.main([]) == 0
    result = payload(capsys)
    with models.get_session() as session:
        owned = session.exec(select(models.Document).where(
            models.Document.application_id == result["applications"]["pass"]["application_id"])).first()
        owned.file_path = "storage/FAKE-unrelated.pdf"
        session.add(owned)
        session.commit()
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    assert tool.main(["--clean"]) == 2
    assert capsys.readouterr().out == "error: STORAGE_UNSAFE\n"
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before


def test_clean_removes_later_owned_files_but_preserves_other_names(isolated_demo, capsys):
    assert tool.main([]) == 0
    result = payload(capsys)
    normal = common.load_application(result["applications"]["pass"]["application_id"])
    own = isolated_demo / "storage" / "documents" / normal.application_no / "FAKE-later.pdf"
    own.write_bytes(b"FAKE-later-owned")
    neighbor = own.parent.parent / f"{normal.application_no}-neighbor.pdf"
    neighbor.write_bytes(b"FAKE-unrelated-neighbor")
    assert tool.main(["--clean"]) == 0
    assert payload(capsys)["deleted_files"] == 15
    assert not own.exists() and neighbor.read_bytes() == b"FAKE-unrelated-neighbor"



def test_dedicated_numbers_preserve_orphaned_ordinary_api_artifacts(isolated_demo, capsys):
    folder = isolated_demo / "storage" / "forms_exports"
    folder.mkdir()
    orphan = folder / "DS-2026-000001.pdf"
    orphan.write_bytes(b"FAKE-old-synthetic-scenario-artifact")
    assert tool.main([]) == 0
    result = payload(capsys)
    for item in result["applications"].values():
        app = common.load_application(item["application_id"])
        assert app.application_no.startswith(tool.NUMBER_PREFIX)
        assert app.application_no != "DS-2026-000001"
    assert orphan.read_bytes() == b"FAKE-old-synthetic-scenario-artifact"
    assert tool.main(["--clean"]) == 0
    assert payload(capsys)["deleted_applications"] == 2
    assert orphan.read_bytes() == b"FAKE-old-synthetic-scenario-artifact"



def test_seed_namespace_works_with_gaps_in_ordinary_api_numbers(isolated_demo, capsys):
    aid = unrelated(isolated_demo)
    with models.get_session() as session:
        existing = session.get(models.Application, aid)
        existing.application_no = "DS-2026-000002"
        session.add(existing)
        session.commit()
    before, files_before = tool._snapshot(), stored_files(isolated_demo)
    assert tool.main([]) == 0
    result = payload(capsys)
    assert result["created"] == 2
    assert all(tool._snapshot().get(key) == value for key, value in before.items())
    for item in result["applications"].values():
        assert common.load_application(item["application_id"]).application_no.startswith(tool.NUMBER_PREFIX)
    assert tool.main(["--clean"]) == 0
    assert payload(capsys)["deleted_applications"] == 2
    assert tool._snapshot() == before and stored_files(isolated_demo) == files_before
