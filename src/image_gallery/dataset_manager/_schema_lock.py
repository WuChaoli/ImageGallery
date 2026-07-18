"""Repo Schema 修改的私有锁组件。"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine

_SCHEMA_LOCK_NAMESPACE = "image-gallery-dataset-schema"


class RepoSchemaLock:
    """按 Repo 隔离本地锁或 PostgreSQL advisory lock。"""

    def __init__(self, engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
        """绑定控制面 Engine 并创建实例内本地锁域。"""
        self._engine = engine
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    @contextmanager
    def hold(self, *, repo_id: str) -> Generator[None, None, None]:
        """在目标 Repo 的 Schema 修改期间持有互斥锁。"""
        if self._engine.dialect.name != "postgresql":
            with self._locks_guard:
                lock = self._locks.setdefault(repo_id, threading.RLock())
            with lock:
                yield
            return

        digest = hashlib.sha256(f"{_SCHEMA_LOCK_NAMESPACE}:{repo_id}".encode()).digest()
        lock_key = int.from_bytes(digest[:8], byteorder="big", signed=True)
        connection = self._engine.connect()
        try:
            connection.execute(text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": lock_key})
            yield
        finally:
            try:
                connection.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": lock_key})
            finally:
                connection.close()
