from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from image_gallery.operators.semantic_provider import (
    OnnxDinoV2SmallProvider,
    SemanticDependencyError,
    SemanticEmbeddingProvider,
    SemanticEmbeddingResult,
    load_semantic_provider,
)


class FakeProvider(SemanticEmbeddingProvider):
    provider_name = "fake"
    provider_version = "1"
    model_id = "fake-model"
    model_path = ""
    base_model = "fake-base"
    embedding_dimension = 3
    embedding_source = "unit"
    normalized = True

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        return SemanticEmbeddingResult(
            embeddings=np.array([[1.0, 0.0, 0.0] for _ in images], dtype=np.float32),
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def test_load_semantic_provider_accepts_named_injected_provider() -> None:
    provider = FakeProvider()

    loaded = load_semantic_provider({"provider": "fake"}, {"fake": provider})

    assert loaded is provider


def test_load_semantic_provider_rejects_unknown_provider_name() -> None:
    with pytest.raises(ValueError, match="unknown semantic provider"):
        load_semantic_provider({"provider": "missing"}, {})


def test_onnx_dinov2_provider_requires_existing_model_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_path = tmp_path / "missing.onnx"

    real_import = __import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "onnxruntime":
            return object()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(ValueError, match="model_path does not exist"):
        OnnxDinoV2SmallProvider(model_path=missing_path)


def test_default_provider_reports_missing_optional_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "onnxruntime":
            raise ImportError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(SemanticDependencyError, match="semantic optional dependencies"):
        load_semantic_provider({"provider": "onnx_dinov2_small"})
