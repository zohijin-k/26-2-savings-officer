"""Synthetic SQLite guard: pre-CAS writers and row replacement cannot silently change a Review."""
from contextlib import closing
import sqlite3

import pytest
from sqlmodel import Session, create_engine, select

from demo.backend import models
from demo.backend.review_revision import update_review

PROGRAM = "double_savings"
COLUMNS = "id, application_id, officer_memo, officer_decision, revision"
INSERT = ("INSERT INTO review (application_id, final_status, review_payload_json, score_json, tiebreak_json, created_at) "
          "VALUES ({app}, 'PASS', '{{}}', '{{}}', '[]', CURRENT_TIMESTAMP)")


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "guard.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(models, "engine", engine)
    models.init_db()
    with Session(engine) as session:
        for aid in (1, 2):
            session.add(models.Application(id=aid, application_no=f"FAKE-GUARD-{aid}", program_code=PROGRAM, status="submitted"))
        session.commit()
        session.add(models.Review(application_id=1, final_status="NEEDS_REVIEW", officer_memo="synthetic officer memo"))
        session.commit()
    yield path
    engine.dispose()


def reviews(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(f"SELECT {COLUMNS} FROM review ORDER BY application_id").fetchall()


def triggers(path):
    with closing(sqlite3.connect(path)) as connection:
        return dict(connection.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"))


def run(path, statement):
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(statement)
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")


def test_init_installs_exact_guards_and_reapplication_is_idempotent(db):
    expected = dict(models.REVIEW_WRITE_GUARDS)
    assert triggers(db) == expected
    for _ in range(2):
        models._add_missing_columns()
    assert triggers(db) == expected


@pytest.mark.parametrize("statement", [
    "UPDATE review SET officer_memo='legacy overwrite' WHERE application_id=1",
    "UPDATE OR IGNORE review SET officer_memo='legacy overwrite' WHERE application_id=1",
    "UPDATE OR REPLACE review SET officer_memo='legacy overwrite' WHERE application_id=1",
    "UPDATE review SET officer_decision='reject'",
    "UPDATE review SET officer_memo='skip', revision=revision+2 WHERE application_id=1",
    "UPDATE review SET officer_memo='same', revision=revision WHERE application_id=1",
    "UPDATE review SET revision=revision-1 WHERE application_id=1",
], ids=["plain", "or-ignore", "or-replace", "bulk", "skip-revision", "same-revision", "rewind-revision"])
def test_update_that_does_not_advance_revision_by_one_is_rejected(db, statement):
    before = reviews(db)
    with pytest.raises(sqlite3.IntegrityError, match="REVIEW_WRITE_GUARD"):
        run(db, statement)
    assert reviews(db) == before


@pytest.mark.parametrize("statement", [
    "INSERT OR REPLACE INTO review (application_id, final_status, review_payload_json, score_json, tiebreak_json, created_at) "
    "VALUES (1, 'PASS', '{}', '{}', '[]', CURRENT_TIMESTAMP)",
    "REPLACE INTO review (id, application_id, final_status, review_payload_json, score_json, tiebreak_json, created_at) "
    "VALUES (1, 2, 'PASS', '{}', '{}', '[]', CURRENT_TIMESTAMP)",
    INSERT.format(app=1),
    "INSERT INTO review (application_id, final_status, officer_memo, review_payload_json, score_json, tiebreak_json, created_at) "
    "VALUES (1, 'PASS', 'upsert', '{}', '{}', '[]', CURRENT_TIMESTAMP) "
    "ON CONFLICT(application_id) DO UPDATE SET officer_memo=excluded.officer_memo, revision=revision+1",
], ids=["insert-or-replace", "replace-same-id", "duplicate", "upsert"])
def test_replacement_or_duplicate_insert_cannot_reset_an_existing_review(db, statement):
    before = reviews(db)
    with pytest.raises(sqlite3.IntegrityError, match="REVIEW_WRITE_GUARD"):
        run(db, statement)
    assert reviews(db) == before


def test_cas_and_orm_writers_and_new_review_creation_still_succeed(db):
    with models.session_transaction():
        with models.get_session() as session:
            assert update_review(session, 1, 1, officer_memo="synthetic CAS memo") == 2
            session.commit()
    with Session(models.engine) as session:
        review = session.exec(select(models.Review).where(models.Review.application_id == 1)).one()
        review.officer_decision = "hold"
        session.add(review)
        session.commit()
        session.add(models.Review(application_id=2, final_status="NEEDS_REVIEW"))
        session.commit()
    run(db, "INSERT INTO application (id, application_no, program_code, status, created_at, updated_at) "
            "VALUES (3, 'FAKE-GUARD-3', 'double_savings', 'submitted', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    run(db, INSERT.format(app=3))
    rows = {row[1]: row for row in reviews(db)}
    assert rows[1][2:] == ("synthetic CAS memo", "hold", 3)
    assert rows[2][4] == 1 and rows[3][4] == 1


@pytest.mark.parametrize("name", [name for name, _ in models.REVIEW_WRITE_GUARDS])
def test_unexpected_guard_definition_stops_migration_without_replacing_it(db, name):
    impostor = f"CREATE TRIGGER {name} AFTER INSERT ON application BEGIN SELECT 1; END"
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(f"DROP TRIGGER {name}")
        connection.execute(impostor)
        connection.commit()
    with pytest.raises(RuntimeError, match="unexpected review write guard"):
        models._add_missing_columns()
    assert triggers(db)[name] == impostor


def test_legacy_database_migration_installs_guards_before_any_legacy_write(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    monkeypatch.setattr(models, "engine", engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE review (id INTEGER PRIMARY KEY, application_id INTEGER, final_status TEXT, "
                                   "officer_decision TEXT, officer_memo TEXT)")
        connection.exec_driver_sql("INSERT INTO review VALUES (1, 10, 'FAIL', 'hold', 'synthetic legacy memo')")
    models._add_missing_columns()
    path = tmp_path / "legacy.db"
    assert triggers(path) == dict(models.REVIEW_WRITE_GUARDS)
    with pytest.raises(sqlite3.IntegrityError, match="REVIEW_WRITE_GUARD"):
        run(path, "UPDATE review SET officer_memo='legacy overwrite' WHERE application_id=10")
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT officer_memo, revision FROM review").fetchone() == ("synthetic legacy memo", 1)
    engine.dispose()


def test_explicit_review_delete_is_a_documented_residual_outside_the_guard(db):
    """DELETE is not guarded: operator deletion tools remove reviews explicitly.

    If a DELETE guard is introduced, change this test together with
    tools/delete_application.py and the seed tools in the same change.
    """
    run(db, "DELETE FROM review WHERE application_id=1")
    assert reviews(db) == []
