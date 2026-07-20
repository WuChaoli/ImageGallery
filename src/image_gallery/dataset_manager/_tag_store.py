"""Repo Tag Definition 的私有持久化组件。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager.control import tag_definitions
from image_gallery.dataset_manager.errors import NameConflictError, ObjectNotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class TagRecord:
    """保存 Tag Definition 的包内持久化记录。"""

    tag_id: str
    repo_id: str
    name: str
    color: str | None
    description: str | None
    archived: bool


class TagStore:
    """持久化 Repo Tag Definition 并校验 active Tag。"""

    def __init__(self, engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
        """绑定控制面数据库 Engine。"""
        self._engine = engine

    def create(
        self,
        *,
        repo_id: str,
        name: str,
        color: str | None,
        description: str | None,
    ) -> TagRecord:
        """在独立事务中创建 Tag Definition。"""
        tag_id = uuid.uuid4().hex
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(tag_definitions).values(
                        tag_id=tag_id,
                        repo_id=repo_id,
                        name=name,
                        name_key=name.casefold(),
                        color=color,
                        description=description,
                        archived=False,
                    )
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return TagRecord(tag_id, repo_id, name, color, description, False)

    def rename(self, *, repo_id: str, tag_id: str, name: str) -> TagRecord:
        """在独立事务中重命名 Repo 内 Tag Definition。"""
        statement = select(tag_definitions).where(
            tag_definitions.c.repo_id == repo_id,
            tag_definitions.c.tag_id == tag_id,
        )
        try:
            with self._engine.begin() as connection:
                row = connection.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ObjectNotFoundError(tag_id)
                connection.execute(
                    update(tag_definitions)
                    .where(tag_definitions.c.repo_id == repo_id, tag_definitions.c.tag_id == tag_id)
                    .values(name=name, name_key=name.casefold())
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return TagRecord(tag_id, repo_id, name, row["color"], row["description"], bool(row["archived"]))

    def archive(self, *, repo_id: str, tag_id: str) -> TagRecord:
        """在独立事务中幂等归档 Repo 内 Tag Definition。"""
        statement = select(tag_definitions).where(
            tag_definitions.c.repo_id == repo_id,
            tag_definitions.c.tag_id == tag_id,
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                raise ObjectNotFoundError(tag_id)
            connection.execute(
                update(tag_definitions)
                .where(tag_definitions.c.repo_id == repo_id, tag_definitions.c.tag_id == tag_id)
                .values(archived=True)
            )
        return TagRecord(tag_id, repo_id, str(row["name"]), row["color"], row["description"], True)

    def validate_active(self, *, repo_id: str, tag_ids: list[str]) -> None:
        """确认全部 Tag 均属于目标 Repo 且未归档。"""
        if not tag_ids:
            return
        statement = select(tag_definitions.c.tag_id).where(
            tag_definitions.c.repo_id == repo_id,
            tag_definitions.c.tag_id.in_(tag_ids),
            tag_definitions.c.archived.is_(False),
        )
        with self._engine.connect() as connection:
            found = set(connection.execute(statement).scalars())
        if found != set(tag_ids):
            raise ValidationError("Unknown or archived tag_id")
