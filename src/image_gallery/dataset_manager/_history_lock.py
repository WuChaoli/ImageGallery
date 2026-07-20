"""Dataset 历史操作的私有串行化锁。"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine

_HISTORY_LOCK_NAMESPACE = "image-gallery-dataset-history"
_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[tuple[str, str], threading.RLock] = {}


class DatasetHistoryLock:
    """按 Backend identity 和 Dataset 隔离历史修改锁。"""

    def __init__(self, engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
        """绑定控制面 Engine。"""
        self._engine = engine
        self._backend_identity = str(engine.url)

    @contextmanager
    def hold(self, *, dataset_id: str) -> Generator[None, None, None]:
        """在目标 Dataset 的历史修改期间持有互斥锁。"""
        if self._engine.dialect.name != "postgresql":
            key = (self._backend_identity, dataset_id)
            with _LOCAL_LOCKS_GUARD:
                lock = _LOCAL_LOCKS.setdefault(key, threading.RLock())
            with lock:
                yield
            return

        digest = hashlib.sha256(f"{_HISTORY_LOCK_NAMESPACE}:{dataset_id}".encode()).digest()
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
