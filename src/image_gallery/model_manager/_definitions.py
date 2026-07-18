"""ModelManager 私有持久化模型。"""

from __future__ import annotations

from typing import TypeAlias, cast

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table
from sqlalchemy.engine import RowMapping

DefinitionFields: TypeAlias = tuple[
    str,
    str,
    str,
    str,
    str,
    int,
    str,
    dict[str, object],
    str | None,
]

metadata = MetaData()
model_definitions = Table(
    "model_definitions",
    metadata,
    Column("model_id", String(128), primary_key=True),
    Column("provider", String(128), nullable=False),
    Column("artifact_uri", String(2048), nullable=False),
    Column("artifact_revision", String(255), nullable=False),
    Column("artifact_checksum", String(128), nullable=False),
    Column("dimension", Integer, nullable=False),
    Column("dtype", String(32), nullable=False),
    Column("config", JSON, nullable=False),
    Column("credential_ref", String(1024), nullable=True),
    Column("fingerprint", String(128), nullable=False),
    schema="control",
)


def definition_fields_from_row(row: RowMapping) -> DefinitionFields:
    """从数据库映射恢复构造公开模型定义所需的字段。"""
    return (
        str(row["model_id"]),
        str(row["provider"]),
        str(row["artifact_uri"]),
        str(row["artifact_revision"]),
        str(row["artifact_checksum"]),
        int(cast(int, row["dimension"])),
        str(row["dtype"]),
        cast(dict[str, object], row["config"]),
        cast(str | None, row["credential_ref"]),
    )
