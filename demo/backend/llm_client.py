"""전북AI(OpenAI 호환 `/chat/completions`) 텍스트 생성 클라이언트.

`26-2-youth/demo/backend/llm_drafts.py`의 전송·로그 규칙을 옮겨 왔다.

- 기본 제공자는 ``none``이다. 키가 있어도 아래 env가 모두 갖춰져야 켜진다.
  ``PROGRAM_LLM_ENABLED=true``, ``PROGRAM_LLM_PROVIDER=jbai``, https
  ``JBAI_BASE_URL``, ``JBAI_API_KEY``.
- 이 모듈은 **무엇을 보낼지 고르지 않는다.** 개인정보 투영은 호출 측
  (`officer_summary.summary_payload`)의 책임이다.
- 로그는 고정 어휘 한 줄뿐이다. 예외 문구·URL·키·프롬프트·응답 본문은 남기지 않는다.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 65_536
MAX_CONTENT_CHARS = 16_000
DEFAULT_TIMEOUT = 30.0

OUTCOMES = ('ok', 'timeout', 'http_429', 'http_4xx', 'http_5xx', 'network', 'bad_transport',
            'no_content', 'truncated', 'too_large', 'bad_shape')
CALL_PURPOSES = ('officer_summary',)
#: json_object → 실패 시 prompt(지시문만)로 한 번 더. youth 측정에서 json_schema는
#: 시간 초과가 잦아 쓰지 않는다.
RESPONSE_FORMATS = ('json_object', 'prompt')
FORMAT_FALLBACK = {'json_object': 'prompt', 'prompt': None}
_log = logging.getLogger('demo.backend.llm')


def failure_outcome(error: BaseException) -> str:
    """예외 종류와 상태 코드만으로 실패 이름을 정한다."""
    if isinstance(error, HTTPError):
        code = error.code if type(error.code) is int else 0
        if code == 429:
            return 'http_429'
        return 'http_5xx' if code >= 500 else 'http_4xx' if code >= 400 else 'bad_transport'
    if isinstance(error, (TimeoutError, socket.timeout)):
        return 'timeout'
    if isinstance(error, URLError):
        return 'timeout' if isinstance(error.reason, (TimeoutError, socket.timeout)) else 'network'
    if isinstance(error, OSError):
        return 'network'
    return 'bad_transport'


def log_call(purpose: str, mode: str, attempt: int, outcome: str, seconds: float) -> None:
    """호출 1건당 한 줄. 실패는 WARNING이라 로깅 설정 없이도 보인다."""
    _log.log(logging.INFO if outcome == 'ok' else logging.WARNING,
             'llm_call purpose=%s mode=%s attempt=%d outcome=%s seconds=%.1f',
             purpose if purpose in CALL_PURPOSES else 'other',
             mode if mode in RESPONSE_FORMATS else 'other',
             attempt if type(attempt) is int else 0,
             outcome if outcome in OUTCOMES else 'bad_transport',
             seconds if type(seconds) in (int, float) and seconds > 0 else 0.0)


class TextProvider(Protocol):
    name: str
    model: str

    def generate(self, purpose: str, messages: Sequence[Mapping[str, str]], *,
                 max_tokens: int = 3000) -> str | None: ...


@dataclass(frozen=True)
class NoneProvider:
    name: str = 'none'
    model: str = ''

    def generate(self, purpose: str, messages: Sequence[Mapping[str, str]], *,
                 max_tokens: int = 3000) -> None:
        return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 예상 밖 리다이렉트로 인증 헤더를 넘기지 않는다.
        return None


def _http_transport(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> Mapping[str, Any]:
    request = Request(url, headers=headers, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), method='POST')
    with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('provider response too large')
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError('provider response is not an object')
    return parsed


JSON_ONLY = ' 응답은 설명이나 코드 블록 없이 JSON 객체 하나만 출력하세요.'


def _has_json_object(text: str) -> bool:
    """응답 어딘가에 JSON 객체가 있는지. 코드펜스·앞뒤 설명은 허용한다."""
    start, end = text.find('{'), text.rfind('}')
    if not 0 <= start < end:
        return False
    try:
        return isinstance(json.loads(text[start:end + 1]), dict)
    except ValueError:
        return False


def _body(model: str, messages: Sequence[Mapping[str, str]], mode: str, max_tokens: int) -> dict[str, Any]:
    copied = [dict(message) for message in messages]
    if mode == 'prompt' and copied and copied[0].get('role') == 'system':
        copied[0]['content'] = copied[0]['content'] + JSON_ONLY
    body: dict[str, Any] = {'model': model, 'messages': copied, 'temperature': 0.1, 'max_tokens': max_tokens}
    if mode == 'json_object':
        body['response_format'] = {'type': 'json_object'}
    return body


@dataclass(frozen=True, repr=False)
class JbaiProvider:
    """키는 생성 시점에만 읽는다. repr에 키가 나오지 않는다."""

    base_url: str
    environ: Mapping[str, str]
    transport: Any = _http_transport
    name: str = 'jbai'
    clock: Any = time.monotonic

    @property
    def model(self) -> str:
        return self.environ.get('JBAI_LLM_MODEL', '').strip() or 'MainModel'

    @property
    def timeout(self) -> float:
        try:
            value = float(self.environ.get('JBAI_LLM_TIMEOUT_SEC', '') or DEFAULT_TIMEOUT)
        except ValueError:
            value = DEFAULT_TIMEOUT
        return min(max(value, 3.0), 120.0)

    def generate(self, purpose: str, messages: Sequence[Mapping[str, str]], *,
                 max_tokens: int = 3000) -> str | None:
        key = self.environ.get('JBAI_API_KEY', '').strip()
        if not key or purpose not in CALL_PURPOSES:
            return None
        mode = self.environ.get('JBAI_RESPONSE_FORMAT', '').strip().lower()
        mode = mode if mode in RESPONSE_FORMATS else 'json_object'
        modes = [mode] + ([FORMAT_FALLBACK[mode]] if FORMAT_FALLBACK[mode] else [])
        for attempt, current in enumerate(modes, 1):
            started = self.clock()
            outcome, content = self._call(key, _body(self.model, messages, current, max_tokens))
            log_call(purpose, current, attempt, outcome, self.clock() - started)
            if outcome == 'ok':
                return content
            if outcome in ('timeout', 'http_429', 'network'):
                # 형식 문제가 아니므로 다른 모드로 다시 불러도 소용없다.
                break
        return None

    def _call(self, key: str, body: dict[str, Any]) -> tuple[str, str | None]:
        try:
            response = self.transport(self.base_url + '/chat/completions',
                                      {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                                      body, self.timeout)
        except Exception as error:
            # 예외 객체에 키·URL·프롬프트가 담길 수 있어 종류만 남긴다.
            return failure_outcome(error), None
        try:
            choice = response['choices'][0]
            content = choice['message']['content']
        except (KeyError, IndexError, TypeError):
            return 'no_content', None
        if type(content) is not str or not content.strip():
            cut = isinstance(choice, Mapping) and choice.get('finish_reason') == 'length'
            return ('truncated' if cut else 'no_content'), None
        if len(content) > MAX_CONTENT_CHARS:
            return 'too_large', None
        if not _has_json_object(content):
            # 모양 확인은 다른 모드로 다시 부를지만 정한다. 내용 검증은 호출 측이 한다.
            cut = isinstance(choice, Mapping) and choice.get('finish_reason') == 'length'
            return ('truncated' if cut else 'bad_shape'), None
        return 'ok', content

    def __repr__(self) -> str:
        return "JbaiProvider(name='jbai')"


def configured_provider(*, environ: Mapping[str, str] | None = None, transport: Any = None) -> TextProvider:
    values = os.environ if environ is None else environ
    enabled = values.get('PROGRAM_LLM_ENABLED', '').strip().lower() in {'true', '1', 'yes'}
    if not enabled or values.get('PROGRAM_LLM_PROVIDER', 'none').strip().lower() != 'jbai':
        return NoneProvider()
    base_url = values.get('JBAI_BASE_URL', '').strip().rstrip('/')
    try:
        url = urlsplit(base_url)
    except ValueError:
        return NoneProvider()
    if (not values.get('JBAI_API_KEY', '').strip() or url.scheme != 'https' or not url.hostname
            or url.username or url.password or url.query or url.fragment):
        return NoneProvider()
    return JbaiProvider(base_url, values, transport or _http_transport)
