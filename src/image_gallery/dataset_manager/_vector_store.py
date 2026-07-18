"""Repo VectorField 与当前向量的私有持久化组件。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager.control import asset_vectors, vector_fields
from image_gallery.dataset_manager.errors import NameConflictError, ObjectNotFoundError


@dataclass(frozen=True, slots=True)
class VectorFieldRecord:
    """保存 VectorField 冻结定义的包内持久化记录。"""

    vector_field_id: str
    repo_id: str
    name: str
    model_id: str
    model_fingerprint: str
    dimension: int
    numeric_type: str
    distance: str


class VectorStore:
    """持久化 VectorField 定义和 Repo 当前向量值。"""

    def __init__(self, engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
        """绑定控制面数据库 Engine。"""
        self._engine = engine

    def create(
        self,
        *,
        repo_id: str,
        name: str,
        name_key: str,
        model_id: str,
        model_fingerprint: str,
        dimension: int,
        numeric_type: str,
        distance: str,
    ) -> VectorFieldRecord:
        """在单个事务中创建冻结 VectorField 定义。"""
        vector_field_id = uuid.uuid4().hex
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(vector_fields).values(
                        vector_field_id=vector_field_id,
                        repo_id=repo_id,
                        name=name,
                        name_key=name_key,
                        model_id=model_id,
                        model_fingerprint=model_fingerprint,
                        dimension=dimension,
                        numeric_type=numeric_type,
                        distance=distance,
                    )
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return VectorFieldRecord(
            vector_field_id,
            repo_id,
            name,
            model_id,
            model_fingerprint,
            dimension,
            numeric_type,
            distance,
        )

    def find_by_name(self, *, repo_id: str, name_key: str, requested_name: str) -> VectorFieldRecord:
        """按 Repo 内规范名称读取 VectorField。"""
        statement = select(vector_fields).where(
            vector_fields.c.repo_id == repo_id,
            vector_fields.c.name_key == name_key,
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(requested_name)
        return self._from_row(row)

    def find_by_id(self, *, repo_id: str, vector_field_id: str) -> VectorFieldRecord:
        """按 Repo 和不可变 ID 读取 VectorField。"""
        statement = select(vector_fields).where(
            vector_fields.c.repo_id == repo_id,
            vector_fields.c.vector_field_id == vector_field_id,
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(vector_field_id)
        return self._from_row(row)

    def list(self, *, repo_id: str) -> list[VectorFieldRecord]:
        """按规范名称列出 Repo 的 VectorField。"""
        statement = select(vector_fields).where(vector_fields.c.repo_id == repo_id).order_by(vector_fields.c.name_key)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._from_row(row) for row in rows]

    def get_current(self, *, repo_id: str, vector_field_id: str, asset_id: str) -> tuple[float, ...] | None:
        """读取单个 Repo 当前向量。"""
        statement = select(asset_vectors.c.value).where(
            asset_vectors.c.repo_id == repo_id,
            asset_vectors.c.vector_field_id == vector_field_id,
            asset_vectors.c.asset_id == asset_id,
        )
        with self._engine.connect() as connection:
            value = connection.execute(statement).scalar_one_or_none()
        if value is None:
            return None
        return tuple(float(component) for component in value)

    def list_current(
        self,
        *,
        repo_id: str,
        vector_field_id: str,
        asset_ids: list[str],
    ) -> dict[str, tuple[float, ...]]:
        """一次查询读取指定资产的 Repo 当前向量。"""
        if not asset_ids:
            return {}
        statement = select(asset_vectors.c.asset_id, asset_vectors.c.value).where(
            asset_vectors.c.repo_id == repo_id,
            asset_vectors.c.vector_field_id == vector_field_id,
            asset_vectors.c.asset_id.in_(asset_ids),
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).all()
        return {
            str(asset_id): tuple(
                float(component) for component in cast("list[float | int | str] | tuple[float | int | str, ...]", value)
            )
            for asset_id, value in rows
        }

    def list_existing(self, *, repo_id: str, vector_field_id: str, asset_ids: list[str]) -> set[str]:
        """一次查询返回已有 Repo 当前向量的资产 ID。"""
        if not asset_ids:
            return set()
        statement = select(asset_vectors.c.asset_id).where(
            asset_vectors.c.repo_id == repo_id,
            asset_vectors.c.vector_field_id == vector_field_id,
            asset_vectors.c.asset_id.in_(asset_ids),
        )
        with self._engine.connect() as connection:
            return {str(value) for value in connection.execute(statement).scalars()}

    def publish_current(
        self,
        *,
        repo_id: str,
        vector_field_id: str,
        values: dict[str, tuple[float, ...]],
        existing: set[str],
    ) -> tuple[int, int]:
        """在单个事务中发布本次生成的全部 Repo 当前向量。"""
        generated = 0
        updated_count = 0
        with self._engine.begin() as connection:
            for asset_id, value in values.items():
                key = (
                    asset_vectors.c.repo_id == repo_id,
                    asset_vectors.c.vector_field_id == vector_field_id,
                    asset_vectors.c.asset_id == asset_id,
                )
                if asset_id in existing:
                    connection.execute(update(asset_vectors).where(*key).values(value=list(value)))
                    updated_count += 1
                else:
                    connection.execute(
                        insert(asset_vectors).values(
                            repo_id=repo_id,
                            vector_field_id=vector_field_id,
                            asset_id=asset_id,
                            value=list(value),
                        )
                    )
                    generated += 1
        return generated, updated_count

    @staticmethod
    def _from_row(row: RowMapping) -> VectorFieldRecord:  # pyright: ignore[reportUnknownParameterType]
        return VectorFieldRecord(
            vector_field_id=str(row["vector_field_id"]),
            repo_id=str(row["repo_id"]),
            name=str(row["name"]),
            model_id=str(row["model_id"] or "legacy"),
            model_fingerprint=str(row["model_fingerprint"] or "legacy"),
            dimension=int(row["dimension"]),
            numeric_type=str(row["numeric_type"]),
            distance=str(row["distance"]),
        )
