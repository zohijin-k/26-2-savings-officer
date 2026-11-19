"""Password authentication for the local officer workspace.

Roles remain presentation scopes selected after login; they are not credentials.
Session tokens contain only issue/expiry times and a random identifier.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import os
import secrets
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

COOKIE_NAME = 'officer_session'
SESSION_SECONDS = 8 * 60 * 60
UNCONFIGURED = '관리자가 .env 에 OFFICER_PASSWORD 를 설정해야 합니다'
router = APIRouter(prefix='/api/officer', tags=['officer authentication'])
_lock = threading.Lock()
_failures: dict[str, tuple[int, float]] = {}
_revoked: dict[str, float] = {}


def _configuration() -> tuple[str, str]:
    return os.environ.get('OFFICER_PASSWORD', ''), os.environ.get('OFFICER_SESSION_SECRET', '')


def configuration_error() -> str | None:
    password, secret = _configuration()
    if not password:
        return UNCONFIGURED
    if not secret:
        return '관리자가 담당자 세션 서명 설정을 완료해야 합니다'
    return None


def _signature(value: str, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), value.encode('ascii'), sha256).hexdigest()


def session_expiry(request: Request) -> int | None:
    """Validate the signed token without returning or logging its contents."""
    if configuration_error():
        return None
    token = request.cookies.get(COOKIE_NAME, '')
    try:
        if len(token) > 256:
            return None
        issued, expires, nonce, signature = token.split('.')
        value = f'{issued}.{expires}.{nonce}'
        issued_at, expires_at = int(issued), int(expires)
        now = time.time()
        _, secret = _configuration()
        if not hmac.compare_digest(_signature(value, secret), signature):
            return None
        if expires_at - issued_at != SESSION_SECONDS or issued_at > now or expires_at <= now or len(nonce) != 32:
            return None
        digest = sha256(token.encode('ascii')).hexdigest()
        with _lock:
            for key, expiry in list(_revoked.items()):
                if expiry <= now:
                    _revoked.pop(key, None)
            if digest in _revoked:
                return None
        return expires_at
    except (ValueError, TypeError, UnicodeError):
        return None


def is_officer(request: Request) -> bool:
    return session_expiry(request) is not None


class LoginBody(BaseModel):
    password: str = Field(max_length=4096)


@router.post('/login')
def login(body: LoginBody, request: Request) -> JSONResponse:
    error = configuration_error()
    if error:
        raise HTTPException(503, error, headers={'Cache-Control': 'no-store'})
    client = request.client.host if request.client else 'local'
    now = time.time()
    with _lock:
        for key, (_, until) in list(_failures.items()):
            if until and until <= now:
                _failures.pop(key, None)
        count, until = _failures.get(client, (0, 0))
        if until > now:
            raise HTTPException(429, '로그인을 잠시 후 다시 시도해 주세요.', headers={'Retry-After': str(max(1, int(until - now + 1))), 'Cache-Control': 'no-store'})
        password, secret = _configuration()
        correct = hmac.compare_digest(sha256(body.password.encode('utf-8')).digest(), sha256(password.encode('utf-8')).digest())
        if not correct:
            count += 1
            _failures[client] = (count, now + 60 if count >= 5 else 0)
            raise HTTPException(401, '비밀번호가 올바르지 않습니다.', headers={'Cache-Control': 'no-store'})
        _failures.pop(client, None)
    issued = int(now)
    expires = issued + SESSION_SECONDS
    value = f'{issued}.{expires}.{secrets.token_hex(16)}'
    response = JSONResponse({'authenticated': True, 'expires_at': expires}, headers={'Cache-Control': 'no-store'})
    response.set_cookie(COOKIE_NAME, f'{value}.{_signature(value, secret)}', max_age=SESSION_SECONDS,
                        path='/api', httponly=True, samesite='lax', secure=request.url.scheme == 'https')
    return response


@router.get('/session')
def current_session(request: Request) -> dict[str, Any]:
    expires = session_expiry(request)
    if expires is None:
        raise HTTPException(401, '담당자 로그인이 필요합니다.')
    return {'authenticated': True, 'expires_at': expires}


@router.post('/logout')
def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(COOKIE_NAME, '')
    expires = session_expiry(request)
    if expires is not None:
        with _lock:
            _revoked[sha256(token.encode('ascii')).hexdigest()] = expires
    response = JSONResponse({'authenticated': False}, headers={'Cache-Control': 'no-store'})
    response.delete_cookie(COOKIE_NAME, path='/api', httponly=True, samesite='lax', secure=request.url.scheme == 'https')
    return response


class OfficerAccess:
    """Guard every officer endpoint, including future routers and unknown paths."""
    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = scope.get('path', '')
        if scope['type'] == 'http' and scope.get('method') != 'OPTIONS' and (path == '/api/officer' or path.startswith('/api/officer/')):
            request = Request(scope)
            error = configuration_error()
            if error:
                response = JSONResponse({'detail': error}, status_code=503, headers={'Cache-Control': 'private, no-store'})
            elif not (path.rstrip('/') == '/api/officer/login' and scope.get('method') == 'POST') and not is_officer(request):
                response = JSONResponse({'detail': '담당자 로그인이 필요합니다.'}, status_code=401, headers={'Cache-Control': 'private, no-store'})
            else:
                await self.app(scope, receive, send)
                return
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
