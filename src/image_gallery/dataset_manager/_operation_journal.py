"""DatasetManager durable operation 的控制面日志。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager._dataset_names import dataset_name_key
from image_gallery.dataset_manager.control import dataset_name_reservations, datasets, operation_phases, operations
from image_gallery.dataset_manager.errors import NameConflictError, ValidationError


@dataclass(frozen=True)
class PendingOperation:
    """描述等待恢复的 durable operation。"""

    operation_id: str
    repo_id: str
    dataset_id: str | None
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

    def start_with_dataset_name_reservation(
        self,
        *,
        kind: str,
        repo_id: str,
        dataset_id: str,
        dataset_name: str,
        intent: dict[str, object],
    ) -> str:
        """原子创建 active operation 并唯一预留 Repo 内 Dataset 名称。"""
        name_key = dataset_name_key(dataset_name)
        operation_id = uuid.uuid4().hex
        try:
            with self._engine.begin() as connection:
                existing = connection.execute(
                    select(datasets.c.dataset_id).where(
                        datasets.c.repo_id == repo_id,
                        datasets.c.name_key == name_key,
                    )
                ).first()
                if existing is not None:
                    raise NameConflictError(dataset_name)
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
                connection.execute(
                    insert(dataset_name_reservations).values(
                        repo_id=repo_id,
                        name_key=name_key,
                        operation_id=operation_id,
                        target_dataset_id=dataset_id,
                    )
                )
        except IntegrityError as exc:
            with self._engine.connect() as connection:
                conflict = connection.execute(
                    select(dataset_name_reservations.c.operation_id).where(
                        dataset_name_reservations.c.repo_id == repo_id,
                        dataset_name_reservations.c.name_key == name_key,
                    )
                ).first()
            if conflict is not None:
                raise NameConflictError(dataset_name) from exc
            raise
        return operation_id

    def release_failed_dataset_name_reservation(self, *, operation_id: str) -> None:
        """显式释放确认未产生 Catalog 副作用的 failed operation 名称预留。"""
        with self._engine.begin() as connection:
            status = connection.execute(
                select(operations.c.status).where(operations.c.operation_id == operation_id)
            ).scalar_one_or_none()
            if status != "failed":
                raise ValidationError("Only a failed operation may release its Dataset name reservation")
            reservation = connection.execute(
                select(dataset_name_reservations.c.operation_id).where(
                    dataset_name_reservations.c.operation_id == operation_id
                )
            ).first()
            if reservation is None:
                raise ValidationError("Operation has no Dataset name reservation")
            connection.execute(
                delete(dataset_name_reservations).where(dataset_name_reservations.c.operation_id == operation_id)
            )

    def pending(self) -> list[PendingOperation]:
        """按 ID 返回全部等待恢复的 operation。"""
        statement = select(operations).where(operations.c.status == "active").order_by(operations.c.operation_id)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._pending_operation(row) for row in rows]

    def get_active(self, *, operation_id: str) -> PendingOperation | None:
        """按 ID 重读仍处于 active 状态的 operation。"""
        statement = select(operations).where(
            operations.c.operation_id == operation_id,
            operations.c.status == "active",
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return None if row is None else self._pending_operation(row)

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
            exists = connection.execute(
                select(operation_phases.c.operation_id).where(
                    operation_phases.c.operation_id == operation_id,
                    operation_phases.c.phase == phase,
                )
            ).first()
            if exists is not None:
                return
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

    def fail(self, *, operation_id: str, blocks_visibility: bool = False) -> None:
        """将 operation 标记为 failed，并按需保留可见性门禁。"""
        if blocks_visibility:
            self.update_intent(operation_id=operation_id, values={"_blocks_visibility": True})
        self._set_status(operation_id=operation_id, status="failed")

    def has_active_dataset_operation(self, *, dataset_id: str) -> bool:
        """返回 Dataset 是否仍有 active 或阻断可见性的失败 operation。"""
        return self.active_for_dataset(dataset_id=dataset_id) is not None

    def active_for_dataset(self, *, dataset_id: str) -> PendingOperation | None:
        """优先返回会改变 Schema 的 active 或阻断可见性的失败 operation。"""
        statement = (
            select(operations)
            .where(
                operations.c.dataset_id == dataset_id,
                operations.c.status.in_(("active", "failed")),
            )
            .order_by(operations.c.operation_id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        pending = [
            self._pending_operation(row)
            for row in rows
            if str(row["status"]) == "active" or bool(cast(dict[str, object], row["intent"]).get("_blocks_visibility"))
        ]
        return next(
            (
                item
                for item in pending
                if item.kind in {"schema", "materialize"} or bool(item.intent.get("schema_additions"))
            ),
            pending[0] if pending else None,
        )

    def _set_status(self, *, operation_id: str, status: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status=status)
            )

    @staticmethod
    def _pending_operation(row: object) -> PendingOperation:
        mapping = cast(dict[str, object], row)
        dataset_id = mapping["dataset_id"]
        return PendingOperation(
            operation_id=str(mapping["operation_id"]),
            repo_id=str(mapping["repo_id"]),
            dataset_id=None if dataset_id is None else str(dataset_id),
            kind=str(mapping["kind"]),
            intent=dict(cast(dict[str, object], mapping["intent"])),
        )
