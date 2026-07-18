"""冻结模型定义与运行时生命周期管理。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy import create_engine, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from image_gallery.model_manager._definitions import (
    definition_fields_from_row,
    metadata,
    model_definitions,
)
from image_gallery.model_manager._runtime import RuntimePool
from image_gallery.model_manager.errors import ModelRegistrationError, ModelRuntimeError


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


class ModelManager:
    """持久化模型定义并管理按需加载的 provider runtime。"""

    def __init__(
        self,
        *,
        engine: Engine | None = None,  # pyright: ignore[reportUnknownParameterType]
        providers: Mapping[str, RuntimeFactory] | None = None,
        credential_provider: CredentialProvider | None = None,
    ) -> None:
        """创建模型管理器；未提供 Engine 时使用进程内 SQLite。"""
        self._owns_engine = engine is None
        self._engine = engine or create_engine("sqlite:///:memory:").execution_options(
            schema_translate_map={"control": None}
        )
        metadata.create_all(self._engine)
        self._providers = dict(providers or {})
        self._credential_provider = credential_provider
        self._runtime_pool = RuntimePool(
            providers=self._providers,
            credential_provider=lambda: self._credential_provider,
        )
        # 保留现有私有诊断入口，runtime 所有权仍由 RuntimePool 管理。
        self._runtimes = self._runtime_pool.runtimes
        self._closed = False

    def register(self, definition: ModelDefinition) -> ModelDefinition:
        """持久化注册冻结定义，相同定义幂等返回。"""
        if definition.dimension <= 0 or definition.dtype != "float32":
            raise ModelRegistrationError("Model dimension and dtype are invalid")
        existing = self.get(model_id=definition.model_id, required=False)
        if existing is not None:
            if existing.fingerprint != definition.fingerprint or existing.credential_ref != definition.credential_ref:
                raise ModelRegistrationError(f"Model ID is bound to another definition: {definition.model_id}")
            return existing
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(model_definitions).values(
                        **asdict(definition),
                        fingerprint=definition.fingerprint,
                    )
                )
        except IntegrityError as exc:
            raise ModelRegistrationError(definition.model_id) from exc
        return definition

    def bind_engine(self, engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
        """把注册表绑定到 DatasetManager 控制数据库并迁移内存定义。"""
        definitions = self._definitions()
        previous_engine = self._engine
        owned_previous_engine = self._owns_engine
        self._engine = engine
        self._owns_engine = False
        metadata.create_all(self._engine)
        for definition in definitions:
            self.register(definition)
        if owned_previous_engine:
            previous_engine.dispose()

    def get(self, *, model_id: str, required: bool = True) -> ModelDefinition | None:
        """按稳定 ID 读取持久化模型定义。"""
        with self._engine.connect() as connection:
            row = (
                connection.execute(select(model_definitions).where(model_definitions.c.model_id == model_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            if required:
                raise ModelRegistrationError(f"Unknown model_id: {model_id}")
            return None
        return ModelDefinition(*definition_fields_from_row(row))

    def embed(self, *, model_id: str, images: list[bytes]) -> list[tuple[float, ...]]:
        """使用冻结定义生成并基础校验一批向量。"""
        if self._closed:
            raise ModelRuntimeError("ModelManager is closed")
        definition = self.get(model_id=model_id)
        if definition is None:
            raise ModelRegistrationError(model_id)
        return self._runtime_pool.embed(definition=definition, images=images)

    def close(self) -> None:
        """关闭全部已加载模型运行时。"""
        if self._closed:
            return
        self._closed = True
        self._runtime_pool.close()
        if self._owns_engine:
            self._engine.dispose()

    def _definitions(self) -> list[ModelDefinition]:
        with self._engine.connect() as connection:
            model_ids = list(connection.execute(select(model_definitions.c.model_id)).scalars())
        definitions: list[ModelDefinition] = []
        for model_id in model_ids:
            definition = self.get(model_id=str(model_id))
            if definition is None:
                raise ModelRegistrationError(str(model_id))
            definitions.append(definition)
        return definitions
