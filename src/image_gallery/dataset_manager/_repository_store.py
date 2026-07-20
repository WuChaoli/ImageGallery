"""DatasetManager Repo、Dataset 与 Prefix 控制面存储。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine, RowMapping

from image_gallery.dataset_manager.control import (
    datasets,
    operations,
    repo_storage_bindings,
    repos,
    storage_prefixes,
)
from image_gallery.dataset_manager.errors import ObjectNotFoundError, ValidationError
from image_gallery.storage_manager import StorageManager, StoragePrefix


@dataclass(frozen=True)
class RepositoryRecord:
    """描述控制面中的 Repo。"""

    repo_id: str
    name: str
    namespace: str


@dataclass(frozen=True)
class DatasetRecord:
    """描述控制面中的 Dataset。"""

    repo_id: str
    dataset_id: str
    name: str
    table_identifier: str


class RepositoryStore:
    """集中读写 Repo、Dataset 与 Storage Prefix 控制面。"""

    def __init__(
        self,
        engine: Engine,  # pyright: ignore[reportUnknownParameterType]
        *,
        storage_manager: StorageManager,
    ) -> None:
        """绑定控制面 Engine 与图片存储管理器。"""
        self._engine = engine
        self._storage_manager = storage_manager

    def add_repo(self, *, record: RepositoryRecord) -> None:
        """新增 Repo 控制面记录。"""
        with self._engine.begin() as connection:
            connection.execute(
                insert(repos).values(
                    repo_id=record.repo_id,
                    name=record.name,
                    name_key=record.name.casefold(),
                    namespace=record.namespace,
                )
            )

    def get_repo_by_name(self, *, name: str) -> RepositoryRecord:
        """按大小写不敏感名称返回 Repo 记录。"""
        statement = select(repos).where(repos.c.name_key == name.casefold())
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(name)
        return self._repository_record(row)

    def get_repo(self, *, repo_id: str) -> RepositoryRecord:
        """按不可变 ID 返回 Repo 记录。"""
        with self._engine.connect() as connection:
            row = connection.execute(select(repos).where(repos.c.repo_id == repo_id)).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(repo_id)
        return self._repository_record(row)

    def list_repos(self) -> list[RepositoryRecord]:
        """按规范名称返回全部 Repo 记录。"""
        with self._engine.connect() as connection:
            rows = connection.execute(select(repos).order_by(repos.c.name_key)).mappings().all()
        return [self._repository_record(row) for row in rows]

    def register_dataset(
        self,
        *,
        operation_id: str,
        record: DatasetRecord,
        name_key: str,
        only_if_missing: bool = False,
    ) -> None:
        """原子登记 Dataset 并完成其 durable operation。"""
        with self._engine.begin() as connection:
            if only_if_missing:
                existing = connection.execute(
                    select(datasets.c.dataset_id).where(datasets.c.dataset_id == record.dataset_id)
                ).first()
            else:
                existing = None
            if existing is None:
                connection.execute(
                    insert(datasets).values(
                        dataset_id=record.dataset_id,
                        repo_id=record.repo_id,
                        name=record.name,
                        name_key=name_key,
                        table_identifier=record.table_identifier,
                    )
                )
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status="finalized")
            )

    def get_dataset_by_name(self, *, repo_id: str, name: str) -> DatasetRecord:
        """按 Repo 与大小写不敏感名称返回 Dataset 记录。"""
        statement = select(datasets).where(
            datasets.c.repo_id == repo_id,
            datasets.c.name_key == name.casefold(),
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(name)
        return self._dataset_record(row)

    def get_dataset(self, *, repo_id: str, dataset_id: str) -> DatasetRecord:
        """按 Repo 与不可变 ID 返回 Dataset 记录。"""
        statement = select(datasets).where(datasets.c.repo_id == repo_id, datasets.c.dataset_id == dataset_id)
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(dataset_id)
        return self._dataset_record(row)

    def list_datasets(self, *, repo_id: str) -> list[DatasetRecord]:
        """按规范名称返回 Repo 中的 Dataset 记录。"""
        statement = select(datasets).where(datasets.c.repo_id == repo_id).order_by(datasets.c.name_key)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._dataset_record(row) for row in rows]

    def bind_storage_prefix(self, *, repo_id: str, prefix_id: str) -> None:
        """持久化 Prefix 冻结定义及 Repo 授权。"""
        prefix = self._storage_manager.get_prefix(prefix_id=prefix_id)
        payload = {
            "name": prefix.name,
            "backend": prefix.backend,
            "root": prefix.root,
            "credential_ref": prefix.credential_ref,
            "endpoint_url": prefix.endpoint_url,
        }
        fingerprint = "sha256:" + hashlib.sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()
        with self._engine.begin() as connection:
            existing_prefix = (
                connection.execute(select(storage_prefixes).where(storage_prefixes.c.prefix_id == prefix_id))
                .mappings()
                .one_or_none()
            )
            if existing_prefix is None:
                connection.execute(
                    insert(storage_prefixes).values(prefix_id=prefix_id, fingerprint=fingerprint, **payload)
                )
            elif str(existing_prefix["fingerprint"]) != fingerprint:
                raise ValidationError(f"Storage Prefix ID is bound to another definition: {prefix_id}")
            existing = connection.execute(
                select(repo_storage_bindings).where(
                    repo_storage_bindings.c.repo_id == repo_id,
                    repo_storage_bindings.c.prefix_id == prefix_id,
                )
            ).first()
            if existing is None:
                connection.execute(insert(repo_storage_bindings).values(repo_id=repo_id, prefix_id=prefix_id))

    def restore_storage_prefixes(self) -> None:
        """将持久化 Prefix 冻结定义恢复到运行时。"""
        with self._engine.connect() as connection:
            rows = connection.execute(select(storage_prefixes)).mappings().all()
        for row in rows:
            self._storage_manager.restore_prefix(
                StoragePrefix(
                    prefix_id=str(row["prefix_id"]),
                    name=str(row["name"]),
                    backend=cast(Literal["file", "s3", "sftp"], str(row["backend"])),
                    root=str(row["root"]),
                    credential_ref=cast(str | None, row["credential_ref"]),
                    endpoint_url=cast(str | None, row["endpoint_url"]),
                )
            )

    def list_storage_prefix_ids(self, *, repo_id: str) -> list[str]:
        """返回 Repo 已授权的 Prefix ID。"""
        statement = (
            select(repo_storage_bindings.c.prefix_id)
            .where(repo_storage_bindings.c.repo_id == repo_id)
            .order_by(repo_storage_bindings.c.prefix_id)
        )
        with self._engine.connect() as connection:
            return list(connection.execute(statement).scalars())

    def has_storage_prefix(self, *, repo_id: str, prefix_id: str) -> bool:
        """返回 Repo 是否已授权指定 Prefix。"""
        statement = select(repo_storage_bindings.c.repo_id).where(
            repo_storage_bindings.c.repo_id == repo_id,
            repo_storage_bindings.c.prefix_id == prefix_id,
        )
        with self._engine.connect() as connection:
            return connection.execute(statement).first() is not None

    @staticmethod
    def _repository_record(row: RowMapping) -> RepositoryRecord:  # pyright: ignore[reportUnknownParameterType]
        return RepositoryRecord(
            repo_id=str(row["repo_id"]),
            name=str(row["name"]),
            namespace=str(row["namespace"]),
        )

    @staticmethod
    def _dataset_record(row: RowMapping) -> DatasetRecord:  # pyright: ignore[reportUnknownParameterType]
        return DatasetRecord(
            repo_id=str(row["repo_id"]),
            dataset_id=str(row["dataset_id"]),
            name=str(row["name"]),
            table_identifier=str(row["table_identifier"]),
        )
