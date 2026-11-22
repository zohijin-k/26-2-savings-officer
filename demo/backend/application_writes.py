"""Serialize application writes across local workers, before reading draft state.

POSIX flock is shared by processes using the same database URL and local temp
filesystem. Keep lock files permanently: unlinking one creates distinct lock
inodes for waiters. This is not a distributed lock for multiple hosts or a
replacement for a database row lock when deploying to a remote database.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import wraps
import fcntl
from hashlib import sha256
import inspect
import os
from pathlib import Path
import tempfile

from . import models

_held = ContextVar("application_write_locks", default=frozenset())


def _key(application_id: int) -> str:
    url = models.engine.url
    # Canonicalize SQLite path aliases so workers agree on the same lock file.
    database = str(Path(url.database).resolve()) if url.drivername.startswith("sqlite") and url.database not in (None, ":memory:") else str(url)
    return sha256(database.encode()).hexdigest() + f"-{application_id}"


def _open(key: str) -> int:
    root = Path(tempfile.gettempdir()) / f"jeonbuk-application-writes-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    return os.open(root / key, os.O_CREAT | os.O_RDWR, 0o600)


@contextmanager
def application_write(application_id: int):
    if models._session_bind.get() is not None:
        # An outer SQLite writer already serializes this service composition.
        # Never acquire a file guard in DB -> file order.
        yield
        return
    key = _key(application_id)
    if key in _held.get():
        yield
        return
    fd = _open(key)
    token = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        token = _held.set(_held.get() | {key})
        yield
    finally:
        if token is not None:
            _held.reset(token)
        os.close(fd)  # Also releases the lock on exceptions/process termination.


@asynccontextmanager
async def application_write_async(application_id: int):
    if models._session_bind.get() is not None:
        # An outer SQLite writer already serializes this service composition.
        # Never acquire a file guard in DB -> file order.
        yield
        return
    key = _key(application_id)
    if key in _held.get():
        yield
        return
    fd = _open(key)
    token = None
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(0.01)
        token = _held.set(_held.get() | {key})
        yield
    finally:
        if token is not None:
            _held.reset(token)
        os.close(fd)


def serialized_application_write(handler):
    """Protect HTTP and direct service calls, including keyword/nested calls."""
    signature = inspect.signature(handler)
    first_parameter = next(iter(signature.parameters))

    def identifier(args, kwargs):
        value = signature.bind(*args, **kwargs).arguments[first_parameter]
        return value.id if isinstance(value, models.Application) else value

    if inspect.iscoroutinefunction(handler):
        @wraps(handler)
        async def asynchronous(*args, **kwargs):
            async with application_write_async(identifier(args, kwargs)):
                return await handler(*args, **kwargs)
        return asynchronous

    @wraps(handler)
    def synchronous(*args, **kwargs):
        with application_write(identifier(args, kwargs)):
            return handler(*args, **kwargs)
    return synchronous
