"""Officer-only review write preconditions. No memo or identity in errors."""
from fastapi import HTTPException
from sqlalchemy import update
from .models import Review

# Keep accepted tokens and their successor exact in JSON/JavaScript and SQLite.
MAX_EXPECTED_REVISION = 9_007_199_254_740_990


def require_revision(expected: int | None) -> int:
    if expected is None:
        raise HTTPException(428, {"code": "REVIEW_REVISION_REQUIRED",
                                  "message": "최신 심사 버전을 조회한 뒤 저장해 주세요."})
    if type(expected) is not int or not 1 <= expected <= MAX_EXPECTED_REVISION:
        raise HTTPException(400, {"code": "REVIEW_REVISION_INVALID",
                                  "message": "유효하지 않은 심사 버전입니다."})
    return expected


def update_review(session, application_id: int, expected: int | None, **values) -> int:
    """Called under session_transaction after authorization/resource/policy checks.

    Application changes and this CAS commit together in the caller's transaction.
    Other ORM writers are covered by Review's version_id_col mapping.
    """
    expected = require_revision(expected)
    if "revision" in values or "application_id" in values or "id" in values:
        raise ValueError("Review identity and revision are server managed")
    result = session.execute(update(Review).where(
        Review.application_id == application_id, Review.revision == expected,
    ).values(**values, revision=Review.revision + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise HTTPException(409, {"code": "REVIEW_REVISION_CONFLICT",
                                  "message": "다른 변경과 충돌했습니다. 최신 심사 상태를 확인해 주세요."})
    return expected + 1
