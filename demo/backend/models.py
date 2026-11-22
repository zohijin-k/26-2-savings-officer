"""데모 DB 스키마 (SQLite + SQLModel).

서식 입력값은 JSON 컬럼 하나에 통째로 넣는다. 데모 단계에서 서식 필드가 계속
바뀌는데 그때마다 마이그레이션을 하는 건 낭비다. 심사·집계에 실제로 쓰이는
값만 P3에서 별도 컬럼으로 승격한다.
"""

from contextlib import asynccontextmanager, contextmanager
import asyncio
import sys
import time
from functools import wraps
import sqlite3

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeoutError
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Column, Integer, UniqueConstraint, text
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Field, Session, SQLModel, create_engine

DB_PATH = Path(__file__).resolve().parents[1] / "demo.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SQLITE_BUSY_TIMEOUT_MS = 5000
_session_bind = ContextVar("demo_session_bind", default=None)
_file_backups = ContextVar("demo_transaction_file_backups", default=None)
_staged_deletes = ContextVar("demo_transaction_staged_deletes", default=None)


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    #: 엔진 `Applicant.applicant_id` 와 같은 키. 담당자가 원본과 매칭하는 유일 키.
    application_no: str = Field(index=True, unique=True)
    program_code: str = Field(index=True)
    #: 신청서 생성 시 고정된 사업 기준 버전. 수정하지 않는다.
    criteria_version: Optional[int] = Field(default=None, index=True)
    #: draft | submitted | reviewing | decided
    status: str = Field(default="draft", index=True)
    #: 서식1 입력값 전체
    form1_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서식2 자가진단 답변 {문항번호: "예"|"아니오"}
    self_check_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서식5 입력값(서명 이미지는 consent 테이블에 별도 저장)
    form5_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 서류 체크리스트를 조립하는 입력 (근로유형·사업장 수·자필서명 여부)
    doc_context_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: 본인인증 결과 {name, birth, phone, method, verified_at, pledge_signature_path}.
    #: 업로드 서류가 '이 신청자의 것인지' 대조하는 기준. 신청서 입력값은 기준이 될 수 없다.
    #: 실서비스는 로그인 시 PASS·간편인증 결과(+CI)가 들어온다. 데모는 method="demo".
    identity_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    #: Applicant-only credentials and immutable submitted-form archive metadata.
    applicant_access_hash: Optional[str] = None
    written_forms_archive_path: Optional[str] = None
    written_forms_archive_count: Optional[int] = None


class ProgramCriteriaVersion(SQLModel, table=True):
    """사업별 심사 기준의 불변 버전 이력."""

    __table_args__ = (UniqueConstraint("program_code", "version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    program_code: str = Field(index=True)
    version: int
    criteria_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    changed_at: datetime = Field(default_factory=datetime.now)
    changed_role: str = "system"


class Consent(SQLModel, table=True):
    """동의 이력.

    수기 서명 없이도 '누가 언제 무엇에 동의했는지'를 남기는 것이 이 테이블의
    존재 이유다. 서식3·4는 체크만, 서식5는 서명 이미지까지 함께 남긴다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: privacy | unique_id | third_party | admin_info
    consent_type: str
    agreed: bool
    #: 서식5 전자서명 PNG 경로 (storage/ 하위). 자필 업로드면 그 파일 경로.
    signature_path: Optional[str] = None
    #: electronic | handwritten
    signature_kind: Optional[str] = None
    agreed_at: datetime = Field(default_factory=datetime.now)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class Document(SQLModel, table=True):
    """업로드 서류 한 건.

    같은 `doc_type`이 여러 슬롯에 올 수 있어(복수 사업장 근로확인서류) 슬롯 키를
    따로 둔다. 병합 PDF를 페이지 단위로 쪼갠 경우 `page_index`와
    `source_file_path`로 원본을 되짚는다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: 체크리스트 슬롯 식별자. 아직 배정되지 않은 병합 페이지는 "unassigned".
    slot_key: str
    #: OCR이 판별한 실제 서류 종류
    doc_type: Optional[str] = None
    #: 이 슬롯이 요구하는 서류 종류 (오분류 판정의 기준값)
    expected_doc_type: Optional[str] = None
    file_path: str
    file_format: str
    declared_issue_date: Optional[date] = None
    ocr_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: PASS | FAIL | NEEDS_REVIEW
    stage1_status: Optional[str] = None
    findings_json: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    #: 병합 PDF에서 쪼갠 경우 원본에서의 페이지 번호(0-based)
    page_index: Optional[int] = None
    #: 병합 PDF 원본 경로
    source_file_path: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)


class SubsidyItem(SQLModel, table=True):
    """취업지원패키지에서 고른 지원 항목 1회차.

    항목별 복수 신청이 가능하므로(사업계획서 "복수선택가능") 회차마다 한 행이다.
    `granted_amount`는 `rules/subsidy.py`가 계산한 실지급액이고, 계산 근거는
    저장하지 않는다 — 한도가 바뀌면 근거 문장도 다시 계산돼야 하기 때문이다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: interview | suit | photo | certificate
    item_type: str
    #: 1-based 회차.
    count_index: int
    #: 정장비 회차가 연결된 면접확인서 회차. 중복 연결은 API에서 거부한다.
    linked_interview_index: Optional[int] = None
    #: 결제영수증 금액(원). 정액 항목(면접비)은 None.
    receipt_amount: Optional[int] = None
    granted_amount: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


_review_revision_column = Column("revision", Integer, nullable=False, default=1, server_default=text("1"))


class Review(SQLModel, table=True):
    """제출 1건의 심사 결과.

    담당자 화면(`09-16-demo-officer`)이 읽는 유일한 테이블이다. 엔진이 만든
    `review_payload`와 데모가 채점한 `ScoreSheet`를 같이 들고 있어야, 담당자가
    "판정 사유"와 "점수 근거"를 한 화면에서 원본과 대조할 수 있다.

    ⚠️ 점수는 신청자에게 노출하지 않는다 (공고문: "평가결과는 공개하지 않음").
    마이페이지 응답(`/status`)은 이 테이블의 점수 컬럼을 절대 싣지 않는다.
    """

    # All ORM updates (including system evidence changes) use SQLAlchemy's CAS.
    __mapper_args__ = {"version_id_col": _review_revision_column}
    __table_args__ = (UniqueConstraint("application_id", name="uq_review_application"),)
    revision: int = Field(default=1, sa_column=_review_revision_column)
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, foreign_key="application.id")
    #: PASS | FAIL | NEEDS_REVIEW (엔진 최종 판정)
    final_status: str = Field(index=True)
    stage1_status: Optional[str] = None
    stage2_status: Optional[str] = None
    #: `rules/scoring.ScoreSheet.as_dict()` — 항목별 basis·source_doc·bbox 포함
    score_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    total_score: Optional[int] = Field(default=None, index=True)
    #: 동점자 정렬 키 (시행지침 우선순위 ①~④)
    tiebreak_json: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    #: 엔진 `run_pipeline` 결과의 심사 요청 패키지 (+ file_ref 주입본)
    review_payload_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    #: 서류 보완 기한. 보완이 허용되는 사업(취업패키지 7일)에서만 채워진다.
    #: 두배적금은 보완 자체가 없으므로 항상 None이다.
    supplement_deadline: Optional[datetime] = None
    #: 담당자 판단 — 여기부터는 officer 태스크가 채운다.
    officer_role: Optional[str] = None
    officer_decision: Optional[str] = None
    officer_memo: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ReviewSummary(SQLModel, table=True):
    """담당자 화면 'AI 종합의견' 캐시 (`officer_summary.py`).

    판정이 아니라 저장된 판정을 풀어 쓴 참고 문구다. `input_hash`는 LLM에 보낸
    투영 입력의 해시라, 판정·서류가 바뀌면 다음 조회에서 다시 생성된다. 전북AI가
    만든 결과만 저장하고, 규칙 기반 대체 요약은 저장하지 않는다.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True, unique=True, foreign_key="application.id")
    input_hash: str
    summary_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    #: jbai (규칙 대체본은 저장하지 않는다)
    source: str
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


#: 병합 PDF 페이지 중 어느 슬롯에도 배정되지 않은 것.
UNASSIGNED_SLOT = "unassigned"

#: 신청 상태. 마이페이지 진행 표시의 단일 소스다.
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_REVIEWING = "reviewing"
STATUS_DECIDED = "decided"


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
    from .rules.criteria import ensure_defaults

    ensure_defaults()


def _add_missing_columns() -> None:
    """데모용 초경량 마이그레이션.

    SQLModel의 `create_all`은 이미 있는 테이블에 컬럼을 추가해 주지 않는다. 데모
    DB를 지웠다 다시 만들면 P1에서 작성한 신청 건이 날아가므로, 빠진 컬럼만
    ALTER로 붙인다. 정식 마이그레이션 도구는 데모 범위 밖이다.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        # Reserve the writer before inspecting legacy rows; SQLite DDL rolls back
        # with this explicit transaction. Never repair duplicate reviews by deletion.
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        if conn.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review'").first():
            duplicate = conn.exec_driver_sql("SELECT application_id FROM review GROUP BY application_id HAVING COUNT(*) > 1 LIMIT 1").first()
            if duplicate:
                raise RuntimeError("Review migration stopped: duplicate application reviews require manual reconciliation")
        for table in SQLModel.metadata.sorted_tables:
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table.name})"))
            }
            if not existing:
                continue
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = ("ALTER TABLE review ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
                       if table.name == "review" and column.name == "revision"
                       else f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type}")
                conn.execute(text(ddl))
        if conn.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review'").first():
            invalid = conn.exec_driver_sql("SELECT 1 FROM review WHERE revision IS NULL OR typeof(revision) != 'integer' OR revision < 1 LIMIT 1").first()
            if invalid:
                raise RuntimeError("Review migration stopped: invalid revision requires manual reconciliation")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS uq_review_application ON review(application_id)")
        conn.commit()


def get_session() -> Session:
    connection = _session_bind.get()
    if connection is not None:
        # Each ORM session has a savepoint inside the real BEGIN IMMEDIATE.
        # A failed flush must not release the outer writer before file restore.
        return Session(connection, join_transaction_mode="create_savepoint")
    return Session(engine)


@contextmanager
def session_transaction(*, join_existing: bool = False, busy_timeout_ms: int | None = None):
    """Own the actual SQLite writer reservation until outer commit/rollback.

    Inner ORM commits release only their savepoint, never the writer. Explicitly joined
    service calls must propagate errors to this owner. Session savepoints retain
    the outer reservation even on flush errors. No row-lock claims or unsupported
    dialect fallback. OCR preparation stays outside.
    """
    existing = _session_bind.get()
    if existing is not None:
        if not join_existing:
            raise RuntimeError("Nested service transactions are unsupported")
        yield existing
        return
    if engine.dialect.name != "sqlite":
        raise HTTPException(503, "지원하지 않는 데이터베이스 설정입니다.")
    try:
        with engine.connect() as connection:
            # Applied per reservation (including test/CLI engines), not only at
            # import time. SQLite manages real-file aliases independently of flock.
            previous_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
            timeout = SQLITE_BUSY_TIMEOUT_MS if busy_timeout_ms is None else busy_timeout_ms
            connection.exec_driver_sql(f"PRAGMA busy_timeout={int(timeout)}")
            try:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            except BaseException:
                connection.exec_driver_sql(f"PRAGMA busy_timeout={int(previous_timeout)}")
                raise
            token = _session_bind.set(connection)
            backups = {}
            backup_token = _file_backups.set(backups)
            staged_deletes = []
            delete_token = _staged_deletes.set(staged_deletes)
            try:
                yield connection
                connection.commit()
            except BaseException:
                # Restore while the writer is still reserved: releasing it first
                # would let another process write before stale bytes are restored.
                try:
                    for original, staged in reversed(staged_deletes):
                        if staged.exists():
                            staged.rename(original)
                    for path, content in reversed(list(backups.items())):
                        if content is None:
                            path.unlink(missing_ok=True)
                        else:
                            path.write_bytes(content)
                finally:
                    connection.rollback()
                raise
            finally:
                _staged_deletes.reset(delete_token)
                _file_backups.reset(backup_token)
                _session_bind.reset(token)
                # PRAGMA is connection-local; busy=0 must not leak to normal
                # pooled read/editor sessions after an async reservation.
                if not connection.invalidated:
                    connection.exec_driver_sql(f"PRAGMA busy_timeout={int(previous_timeout)}")
    except StaleDataError:
        raise HTTPException(409, {"code": "REVIEW_REVISION_CONFLICT",
                                  "message": "심사 기록이 변경되었습니다. 최신 상태를 확인해 주세요."}) from None
    except (DBAPIError, PoolTimeoutError) as exc:
        # Busy/locked are retryable. Other operational failures stay sanitized,
        # but do not advertise retries for corruption/schema/read-only errors.
        original = getattr(exc, "orig", None)
        code = getattr(original, "sqlite_errorcode", 0) & 0xff
        if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise DatabaseBusy() from None
        if isinstance(exc, PoolTimeoutError):
            raise HTTPException(503, "일시적으로 저장할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                                headers={"Retry-After": "1"}) from None
        if isinstance(original, sqlite3.OperationalError):
            raise HTTPException(503, "데이터 저장소에 연결할 수 없습니다.") from None
        raise


class DatabaseBusy(HTTPException):
    def __init__(self):
        super().__init__(503, "일시적으로 저장할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                         headers={"Retry-After": "1"})


@asynccontextmanager
async def async_session_transaction():
    """Cancellable SQLite writer acquisition without a background lock waiter.

    Busy attempts release their connection before yielding to the event loop.
    After acquisition, finalization contains no await except the explicit
    cancellation checkpoint, so cancellation rolls back before any mutation.
    """
    deadline = time.monotonic() + SQLITE_BUSY_TIMEOUT_MS / 1000
    while True:
        transaction = session_transaction(join_existing=True, busy_timeout_ms=0)
        try:
            connection = transaction.__enter__()
            break
        except DatabaseBusy:
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(.01)
    try:
        await asyncio.sleep(0)
        yield connection
    except BaseException:
        transaction.__exit__(*sys.exc_info())
        raise
    else:
        transaction.__exit__(None, None, None)


def transactional_write(handler):
    """Short synchronous mutation; acquisition precedes every state/policy read.

    Use explicit session_transaction around async upload finalization so byte
    and image preparation do not occupy SQLite's single writer reservation.
    """
    @wraps(handler)
    def wrapped(*args, **kwargs):
        with session_transaction(join_existing=True):
            return handler(*args, **kwargs)
    return wrapped


def preserve_file_on_rollback(path: Path) -> None:
    """Remember generated output bytes for normal exceptions, never crash recovery.

    Only called for small generated signatures/form archives, under the writer
    reservation. Upload originals retain their UUID/staging rollback protocol.
    """
    backups = _file_backups.get()
    if backups is not None and path not in backups:
        backups[path] = path.read_bytes() if path.exists() else None


def stage_file_deletion(original: Path, staged: Path) -> None:
    """Keep reversible rename restoration inside the reserved DB transaction."""
    staged_deletes = _staged_deletes.get()
    if staged_deletes is None:
        raise RuntimeError("File deletion requires an owned write transaction")
    staged_deletes.append((original, staged))
    original.rename(staged)
