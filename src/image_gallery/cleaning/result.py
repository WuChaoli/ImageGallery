"""Cleaner result primitives."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


def read_result_status(cache_root: Path, run_id: str) -> str:
    """读取 `run_state.sqlite` 中的运行状态。"""
    database_path = Path(cache_root) / run_id / "run_state.sqlite"
    if not database_path.exists():
        return "running"

    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT status FROM cleaning_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return "running"
        return str(row[0])
    finally:
        connection.close()


@dataclass(frozen=True)
class CleanerResult:
    """清洗一次运行后的最小可见返回对象。"""

    run_id: str
    cache_root: Path

    def status(self) -> str:
        """返回运行状态的可读摘要。"""
        return read_result_status(self.cache_root, self.run_id)
