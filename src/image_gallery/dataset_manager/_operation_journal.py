"""DatasetManager durable operation 的控制面日志。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from image_gallery.dataset_manager.control import operation_phases, operations


@dataclass(frozen=True)
class PendingOperation:
    """描述等待恢复的 durable operation。"""

    operation_id: str
    kind: str
    intent: dict[str, object]


class OperationJournal:
    """集中持久化 operation intent、阶段和终态。"""

    def __init__(
        self,
        engine: Engine,  # pyright: ignore[reportUnknownParameterType]
        *,
        operation_hook: Callable[[str, str], None] | None = None,
    ) -> None:
        """绑定控制面 Engine 和可选阶段回调。"""
        self._engine = engine
        self._operation_hook = operation_hook

    def start(
        self,
        *,
        kind: str,
        repo_id: str,
        dataset_id: str | None,
        intent: dict[str, object],
    ) -> str:
        """创建 active operation 并返回其 ID。"""
        operation_id = uuid.uuid4().hex
        with self._engine.begin() as connection:
            connection.execute(
                insert(operations).values(
                    operation_id=operation_id,
                    repo_id=repo_id,
                    dataset_id=dataset_id,
                    kind=kind,
                    status="active",
                    intent=intent,
                )
            )
        return operation_id

    def pending(self) -> list[PendingOperation]:
        """按 ID 返回全部等待恢复的 operation。"""
        statement = select(operations).where(operations.c.status == "active").order_by(operations.c.operation_id)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [
            PendingOperation(
                operation_id=str(row["operation_id"]),
                kind=str(row["kind"]),
                intent=dict(cast(dict[str, object], row["intent"])),
            )
            for row in rows
        ]

    def update_intent(self, *, operation_id: str, values: dict[str, object]) -> None:
        """合并更新 operation 的 durable intent。"""
        with self._engine.begin() as connection:
            stored_intent = connection.execute(
                select(operations.c.intent).where(operations.c.operation_id == operation_id)
            ).scalar_one()
            intent = dict(cast(dict[str, object], stored_intent))
            intent.update(values)
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(intent=intent)
            )

    def record_phase(
        self,
        *,
        operation_id: str,
        phase: str,
        details: dict[str, object] | None = None,
    ) -> None:
        """持久化已完成阶段，并在提交后触发阶段回调。"""
        with self._engine.begin() as connection:
            connection.execute(
                insert(operation_phases).values(
                    operation_id=operation_id,
                    phase=phase,
                    status="complete",
                    details=details,
                )
            )
        if self._operation_hook is not None:
            self._operation_hook(operation_id, phase)

    def finalize(self, *, operation_id: str) -> None:
        """将 operation 标记为 finalized。"""
        self._set_status(operation_id=operation_id, status="finalized")

    def fail(self, *, operation_id: str) -> None:
        """将 operation 标记为 failed。"""
        self._set_status(operation_id=operation_id, status="failed")

    def has_active_dataset_operation(self, *, dataset_id: str) -> bool:
        """返回 Dataset 是否仍有 active operation。"""
        statement = select(operations.c.operation_id).where(
            operations.c.dataset_id == dataset_id,
            operations.c.status == "active",
        )
        with self._engine.connect() as connection:
            return connection.execute(statement).first() is not None

    def _set_status(self, *, operation_id: str, status: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status=status)
            )
