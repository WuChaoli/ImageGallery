"""ModelManager 私有冻结定义与持久化模型。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Protocol, cast

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table
from sqlalchemy.engine import RowMapping


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    """描述可持久化且不可变的 embedding 模型定义。"""

    model_id: str
    provider: str
    artifact_uri: str
    artifact_revision: str
    artifact_checksum: str
    dimension: int
    dtype: str
    config: dict[str, object]
    credential_ref: str | None = None

    @property
    def fingerprint_payload(self) -> str:
        """返回排除凭证引用的规范指纹载荷。"""
        payload = asdict(self)
        payload.pop("credential_ref")
        payload.pop("model_id")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def fingerprint(self) -> str:
        """返回冻结模型定义的 SHA-256 指纹。"""
        return "sha256:" + hashlib.sha256(self.fingerprint_payload.encode()).hexdigest()


class ModelRuntime(Protocol):
    """定义 provider 加载后的最小运行时接口。"""

    def embed(self, images: list[bytes]) -> list[tuple[float, ...]]:
        """为一批图片生成向量。"""
        ...

    def close(self) -> None:
        """释放模型运行时资源。"""


CredentialProvider = Callable[[str], Mapping[str, object]]
RuntimeFactory = Callable[[ModelDefinition, Mapping[str, object]], ModelRuntime]

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


def definition_from_row(row: RowMapping) -> ModelDefinition:
    """从数据库映射恢复冻结模型定义。"""
    return ModelDefinition(
        model_id=str(row["model_id"]),
        provider=str(row["provider"]),
        artifact_uri=str(row["artifact_uri"]),
        artifact_revision=str(row["artifact_revision"]),
        artifact_checksum=str(row["artifact_checksum"]),
        dimension=int(cast(int, row["dimension"])),
        dtype=str(row["dtype"]),
        config=cast(dict[str, object], row["config"]),
        credential_ref=cast(str | None, row["credential_ref"]),
    )
