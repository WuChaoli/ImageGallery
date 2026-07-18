"""ModelManager 私有 provider runtime 生命周期。"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

from image_gallery.model_manager._definitions import (
    CredentialProvider,
    ModelDefinition,
    ModelRuntime,
    RuntimeFactory,
)
from image_gallery.model_manager.errors import ModelRuntimeError


class RuntimePool:
    """按模型缓存 provider runtime 并校验批量输出。"""

    def __init__(
        self,
        *,
        providers: Mapping[str, RuntimeFactory],
        credential_provider: Callable[[], CredentialProvider | None],
    ) -> None:
        """绑定 provider 工厂和动态凭证解析器。"""
        self._providers = providers
        self._credential_provider = credential_provider
        self.runtimes: dict[str, ModelRuntime] = {}

    def embed(self, *, definition: ModelDefinition, images: list[bytes]) -> list[tuple[float, ...]]:
        """复用 runtime 执行推理，并整批校验输出。"""
        outputs = self._runtime(definition).embed(images)
        if len(outputs) != len(images):
            raise ModelRuntimeError("Model output count does not match input count")
        return [self._normalize_output(definition=definition, output=output) for output in outputs]

    def close(self) -> None:
        """关闭全部已加载 runtime 并清空缓存。"""
        for runtime in self.runtimes.values():
            runtime.close()
        self.runtimes.clear()

    def _runtime(self, definition: ModelDefinition) -> ModelRuntime:
        runtime = self.runtimes.get(definition.model_id)
        if runtime is not None:
            return runtime
        factory = self._providers.get(definition.provider)
        if factory is None:
            raise ModelRuntimeError(f"Model provider is unavailable: {definition.provider}")
        secrets: Mapping[str, object] = {}
        if definition.credential_ref is not None:
            credential_provider = self._credential_provider()
            if credential_provider is None:
                raise ModelRuntimeError("Model credential provider is unavailable")
            secrets = credential_provider(definition.credential_ref)
        runtime = factory(definition, secrets)
        self.runtimes[definition.model_id] = runtime
        return runtime

    @staticmethod
    def _normalize_output(*, definition: ModelDefinition, output: tuple[float, ...]) -> tuple[float, ...]:
        try:
            value = tuple(float(component) for component in output)
        except (TypeError, ValueError) as exc:
            raise ModelRuntimeError("Model output dtype is invalid") from exc
        if len(value) != definition.dimension or not all(math.isfinite(component) for component in value):
            raise ModelRuntimeError("Model output dimension or finite-value contract failed")
        return value
