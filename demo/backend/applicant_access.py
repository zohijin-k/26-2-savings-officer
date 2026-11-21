"""신청자 소유자 쿠키 검사.

`/api/applications/{신청 번호}/…`와 `/api/files/{문서 번호}`는 그 신청을 만든
브라우저의 소유자 쿠키(`applicant_access_{신청 번호}`)가 있어야 라우터에 닿는다.
로그인한 담당자는 원본(`GET /api/files/…`)만 볼 수 있다. 담당자 세션으로 신청자
경로를 읽거나 바꿀 수는 없다.

youth `generic_access.py`에서 범용 사업, 공개 빈 서식, 이전 쿠키 넓히기, 쓰기
잠금을 뺀 것이다. 규격은 `.trellis/spec/backend/access-control.md`.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
from typing import Any

from pydantic import TypeAdapter, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .application_writes import application_write_async
from .models import Application, Document, get_session
from .officer_auth import is_officer

DENIED = "신청자 본인만 접근할 수 있습니다."
_INTEGER = TypeAdapter(int)


def _route_id(segment: str) -> int | None:
    # 라우터와 같은 정수 변환을 쓴다(+1, 01, 1.0 도 같은 번호). 숫자 모양만 보면
    # 다른 표기로 쓴 주소가 검사를 비켜 간다.
    try:
        value = _INTEGER.validate_python(segment)
    except (ValidationError, ValueError, TypeError):
        return None
    return value if 0 < value < 2**63 else None


def _application_for_path(parts: list[str]) -> Application | None:
    identifier = _route_id(parts[3])
    if identifier is None:
        return None
    with get_session() as session:
        if parts[2] == "files":
            document = session.get(Document, identifier)
            if document is None:
                return None
            identifier = document.application_id
        return session.get(Application, identifier)


def _is_owner(application: Application | None, request: Request) -> bool:
    if application is None:
        return False
    token = request.cookies.get(f"applicant_access_{application.id}", "")
    expected = application.applicant_access_hash or ""
    if not token or not expected:
        return False
    return hmac.compare_digest(sha256(token.encode("utf-8")).hexdigest(), expected)


class ApplicantAccess:
    """신청 번호가 붙은 신청자 경로와 원본 경로를 소유자에게만 연다.

    신청 만들기(`POST /api/applications`)처럼 번호가 없는 경로는 검사하지 않는다.
    번호가 정수가 아니거나 없는 신청·서류도 같은 403이라 존재 여부가 드러나지 않는다.
    """

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        parts = scope.get("path", "").split("/")
        if not (len(parts) >= 4 and parts[1] == "api" and parts[2] in {"applications", "files"}):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        if parts[2] == "files" and scope.get("method") == "GET" and is_officer(request):
            await self.app(scope, receive, send)
            return
        if not _is_owner(_application_for_path(parts), request):
            response = JSONResponse({"detail": DENIED}, status_code=403,
                                    headers={"Cache-Control": "private, no-store"})
            await response(scope, receive, send)
            return
        if parts[2] == "applications" and scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
            # Include signature scans/consents and written-form changes so an
            # earlier request cannot finish after the submission snapshot.
            async with application_write_async(_route_id(parts[3])):
                await self.app(scope, receive, send)
            return
        await self.app(scope, receive, send)
