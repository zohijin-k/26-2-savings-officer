"""문서 자동 판독(OCR) 실행 게이트 (11-28): 이벤트 루프 밖 전용 작업 스레드 + 프로세스별 동시 실행·대기 상한.

전에는 업로드 처리(async)가 판독을 이벤트 루프에서 직접 돌렸다. 한 건을 읽는 동안(30쪽 잡음 스캔 약 1분) 그 서버
프로세스의 다른 요청이 모두 멈췄고(`/api/health` 포함), 멈춘 동안 DB 쓰기 대기 시한이 지나 503이 났다.

지금은 판독을 전용 작업 스레드 하나에서 돌린다. 이 파일은 두배적금·youth 백엔드에서 같은 내용이다.

- **동시 판독은 프로세스당 1건**(`MAX_CONCURRENT_READS`). 환경변수로 늘릴 수 없다. 근거: 문서 한 건이 이미 쪽 단위로
  최대 4개 작업 × ONNX 스레드 2개를 써서 8코어를 채우고(20쪽 500~590%), 판독 중인 쪽 세션마다 약 0.35GB를 쓴다. 문서 두
  건을 함께 읽으면 스레드가 코어의 두 배가 되고 메모리도 겹친다. PyMuPDF도 여러 스레드에서 쓰는 것을 지원하지 않는다.
  **처리량은 늘지 않는다** — 판독은 지금처럼 한 건씩이고, 다른 요청이 기다리지 않게 될 뿐이다.
- **대기 상한**(`OCR_MAX_WAITING_READS`, 기본 8건): 판독 중인 1건 말고 차례를 기다리는 업로드 수. 넘으면 파일을
  저장하기 **전에** 503(Retry-After)으로 거절한다.
- **대기 시한**(`OCR_MAX_QUEUE_WAIT_SECONDS`, 기본 90초): 차례가 오지 않은 업로드는 시작하지 않고 503으로 돌려보낸다.
  신청 화면은 업로드 응답을 120초까지만 기다린다. 90초 넘게 기다린 요청은 20쪽 문서(판독 15~25초)도 그 안에 끝내지
  못하므로 읽지 않는다. 시한 안에 시작한 판독은 끝까지 읽고 저장한다(화면이 먼저 포기했어도 결과는 남는다).
- **취소**: 요청이 취소되면 아직 시작하지 않은 판독은 실행하지 않는다. **이미 시작한 판독은 멈출 수 없다**(파이썬 스레드는
  밖에서 중단되지 않는다). 그 판독이 실제로 끝날 때까지 자리를 차지한 것으로 세고, 결과는 버린다. 판독 자체의 시간
  한도(`engine_v2.pipeline.limits.MAX_OCR_SECONDS`)가 그 길이를 묶는다.
- 상한은 **프로세스별**이다. 서버 프로세스(uvicorn worker)를 여러 개 띄우면 프로세스마다 1건씩 동시에 읽고 모델도
  프로세스마다 따로 올린다. 여러 프로세스·여러 서버에 걸친 전체 상한은 여기서 보장하지 않는다.

판독 함수는 요청의 contextvars(신청 쓰기 잠금 표시 등)를 복사한 문맥에서 돈다. DB 쓰기 예약(BEGIN IMMEDIATE) 안에서
부르지 않는다 — 판독은 지금처럼 예약 밖에서 끝내고 저장만 예약 안에서 한다.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Callable

from fastapi import HTTPException

_log = logging.getLogger(__name__)

#: 이 프로세스가 동시에 판독하는 문서 수. 설정값이 아니다(위 설명).
MAX_CONCURRENT_READS = 1


def _env_number(name: str, default: int) -> int:
    """환경변수의 0 이상 정수. 없거나 형식이 다르면 기본값(값은 로그에 남기지 않는다)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    if re.fullmatch("[0-9]{1,6}", raw):
        return int(raw)
    _log.warning("%s is not a non-negative integer; using default %d", name, default)
    return default


#: 판독 차례를 기다릴 수 있는 업로드 수(판독 중인 건 제외). 0이면 판독 중일 때 온 업로드를 바로 거절한다.
MAX_WAITING_READS = _env_number("OCR_MAX_WAITING_READS", 8)
#: 차례를 기다리는 최대 시간(초). 0이면 시한 없음.
MAX_QUEUE_WAIT_SECONDS = _env_number("OCR_MAX_QUEUE_WAIT_SECONDS", 90)
#: 503 응답의 Retry-After(초).
RETRY_AFTER_SECONDS = 10

BUSY_MESSAGE = "지금 서류 자동 확인 요청이 많습니다. 잠시 후 다시 올려 주세요."


class OcrBusy(HTTPException):
    """판독 대기열이 가득 찼거나 차례가 시한 안에 오지 않았다. 이 업로드는 저장되지 않았다."""

    def __init__(self) -> None:
        super().__init__(503, BUSY_MESSAGE, headers={"Retry-After": str(RETRY_AFTER_SECONDS)})


class _Gate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._admitted = 0  # 자리를 받은 업로드(대기 + 판독 중 + 취소됐지만 아직 도는 판독)
        #: 프로세스가 사는 동안 하나만 둔다. 다시 만들지 않는다 — 새로 만들면 앞 스레드의 판독이 끝나기 전에 다음 판독이
        #: 시작돼 '동시 1건'이 깨진다.
        self._executor: ThreadPoolExecutor | None = None
        self._pending: set[Future] = set()  # 맡긴 판독(대기 + 실행 중)
        self._reading_since: float | None = None

    def admit(self) -> "OcrTicket":
        with self._lock:
            if self._admitted >= MAX_CONCURRENT_READS + MAX_WAITING_READS:
                age = -1 if self._reading_since is None else int(time.monotonic() - self._reading_since)
                _log.warning("OCR 대기열 가득: 업로드 거절 (자리 %d, 진행 중인 판독 %d초째)", self._admitted, age)
                raise OcrBusy()
            self._admitted += 1
        return OcrTicket(self)

    def release(self) -> None:
        with self._lock:
            self._admitted -= 1

    def submit(self, job: Callable[[], Any]) -> Future:
        def tracked() -> Any:
            with self._lock:
                self._reading_since = time.monotonic()
            try:
                return job()
            finally:
                with self._lock:
                    self._reading_since = None

        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(MAX_CONCURRENT_READS, thread_name_prefix="ocr-read")
            future = self._executor.submit(tracked)
            self._pending.add(future)
        future.add_done_callback(self._forget)
        return future

    def _forget(self, future: Future) -> None:
        with self._lock:
            self._pending.discard(future)

    def shutdown(self) -> None:
        with self._lock:
            pending = list(self._pending)
        for future in pending:
            future.cancel()  # 대기 중인 판독만 취소된다. 실행 중인 판독은 끝까지 돈다(멈출 수 없다).

    def admitted(self) -> int:
        with self._lock:
            return self._admitted

    def reading_seconds(self) -> float | None:
        with self._lock:
            return None if self._reading_since is None else time.monotonic() - self._reading_since


_gate = _Gate()


class OcrTicket:
    """판독 자리 하나. `reserve()`로 받고, `run`으로 판독 한 번을 작업 스레드에서 돌린다."""

    def __init__(self, gate: _Gate) -> None:
        self._gate = gate
        self._lock = threading.Lock()
        self._in_flight = False  # 작업 스레드에 맡긴 판독이 아직 끝나지 않았다(대기 또는 실행 중)
        self._used = False
        self._closed = False
        self._released = False
        self._cleanups: list[Callable[[], None]] = []

    async def run(self, function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        """`function(*args, **kwargs)`를 판독 작업 스레드에서 돌리고 결과를 기다린다(자리당 한 번).

        판독은 이벤트 루프 스레드에서 돌지 않는다(판독 스레드가 GIL을 쥔 C 호출을 하는 동안의 짧은 지연은 남는다).
        차례가 시한 안에 오지 않으면 시작하지 않고 `OcrBusy`. 기다리는 요청이 취소되면 아직 시작하지 않은 판독은
        실행하지 않고, 이미 시작한 판독은 끝까지 돈 뒤 결과를 버린다. 서버 종료가 대기 중인 판독을 버리면 `OcrBusy`.
        """
        with self._lock:
            if self._used or self._closed:
                raise RuntimeError("an OCR ticket runs one read")
            self._used = self._in_flight = True
        context = contextvars.copy_context()
        try:
            future = self._gate.submit(lambda: context.run(function, *args, **kwargs))
        except BaseException:
            self._done(None)
            raise
        future.add_done_callback(self._done)
        waiter = asyncio.wrap_future(future)
        try:
            if MAX_QUEUE_WAIT_SECONDS:
                finished, _ = await asyncio.wait({waiter}, timeout=MAX_QUEUE_WAIT_SECONDS)
                if not finished and future.cancel():  # 아직 대기 중이었다: 실행하지 않는다.
                    _log.warning("OCR 차례 대기 시한 초과: 업로드를 읽지 않고 돌려보냄")
                    raise OcrBusy()
            return await waiter
        except asyncio.CancelledError:
            dropped = future.cancelled()  # 이 요청이 아니라 서버 종료(shutdown)가 대기 중인 판독을 버렸는가
            future.cancel()  # 대기 중이면 실행하지 않는다. 실행 중이면 효과가 없다(끝나면 _done이 자리를 놓는다).
            waiter.cancel()  # 버린 판독의 결과·예외를 아무도 받지 않아도 경고가 남지 않게.
            task = asyncio.current_task()
            if dropped and task is not None and not task.cancelling():
                raise OcrBusy() from None
            raise
        except BaseException:
            future.cancel()
            waiter.cancel()
            raise

    def after_read(self, cleanup: Callable[[], None]) -> None:
        """`cleanup`을 판독이 작업 스레드에서 **실제로 끝난 뒤** 부른다(맡긴 판독이 없거나 이미 끝났으면 지금).

        취소된 요청이 판독 중인 파일을 지우지 않게 한다: 파일 정리는 그 파일을 읽는 스레드가 끝난 다음이다.
        """
        with self._lock:
            if self._in_flight:
                self._cleanups.append(cleanup)
                return
        cleanup()

    def close(self) -> None:
        """요청 처리가 끝났다. 맡긴 판독이 아직 돌고 있으면 자리는 그 판독이 끝날 때 놓는다."""
        with self._lock:
            self._closed = True
            release = not self._in_flight and not self._released
            if release:
                self._released = True
        if release:
            self._gate.release()

    def _done(self, _future: Future | None) -> None:
        """판독이 끝났다(정상·예외·시작 전 취소). 작업 스레드나 취소한 스레드에서 불린다."""
        with self._lock:
            self._in_flight = False
            cleanups, self._cleanups = self._cleanups, []
            release = self._closed and not self._released
            if release:
                self._released = True
        try:
            for cleanup in cleanups:
                try:
                    cleanup()
                except Exception as exc:  # noqa: BLE001 - 버려진 요청의 정리 실패는 기록만 한다(예외 문장 제외).
                    _log.warning("판독 뒤 정리 실패: %s", type(exc).__name__)
        finally:
            if release:
                self._gate.release()


@contextmanager
def reserve():
    """판독 자리를 하나 잡는다. 대기열이 가득하면 `OcrBusy`(503) — 호출하는 쪽은 그 전에 아무것도 저장하지 않는다."""
    ticket = _gate.admit()
    try:
        yield ticket
    finally:
        ticket.close()


def shutdown() -> None:
    """서버 종료: 차례를 기다리는 판독을 버린다(기다리던 요청은 503). 실행 중인 판독은 멈출 수 없어 끝까지 돈다.

    작업 스레드는 프로세스가 끝날 때까지 하나를 그대로 쓴다. 종료 뒤 다시 기동해도(시험) 앞 판독이 끝난 다음에 읽는다.
    """
    _gate.shutdown()


def admitted() -> int:
    """자리를 차지한 업로드 수(대기 + 판독 중 + 취소됐지만 아직 도는 판독). 시험·진단용."""
    return _gate.admitted()


def reading_seconds() -> float | None:
    """지금 판독 중인 문서가 읽기 시작한 뒤 지난 시간(초). 판독 중이 아니면 None. 진단용."""
    return _gate.reading_seconds()
