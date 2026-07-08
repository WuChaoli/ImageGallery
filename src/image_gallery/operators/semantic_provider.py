from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class SemanticDependencyError(RuntimeError):
    """语义去重可选依赖缺失。"""


@dataclass(frozen=True)
class SemanticEmbeddingResult:
    """语义 embedding provider 的批量输出。"""

    embeddings: NDArray[np.float32]
    provider_name: str
    provider_version: str
    model_id: str
    model_path: str
    base_model: str
    embedding_dimension: int
    embedding_source: str
    normalized: bool


@runtime_checkable
class SemanticEmbeddingProvider(Protocol):
    """图片语义 embedding provider 协议。"""

    provider_name: str
    provider_version: str
    model_id: str
    model_path: str
    base_model: str
    embedding_dimension: int
    embedding_source: str
    normalized: bool

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        """把图片批量转换为二维 embedding。"""


class OnnxDinoV2SmallProvider:
    """基于 ONNX Runtime 的 DINOv2-small 图片 embedding provider。"""

    provider_name = "onnx_dinov2_small"
    provider_version = "1"
    model_id = "onnx-community/dinov2-small-ONNX"
    base_model = "facebook/dinov2-small"
    embedding_dimension = 384
    embedding_source = "cls_token"
    normalized = True

    def __init__(self, model_path: str | Path | None = None) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise SemanticDependencyError(
                "semantic optional dependencies are required; install image-gallery[semantic]"
            ) from exc
        resolved_path = _resolve_model_path(model_path, self.model_id)
        self.model_path = str(resolved_path)
        self._session = ort.InferenceSession(str(resolved_path), providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        """运行 DINOv2-small ONNX 模型并返回归一化 cls token embedding。"""
        embeddings: NDArray[np.float32]
        if not images:
            embeddings = np.empty((0, self.embedding_dimension), dtype=np.float32)
        else:
            batch = np.stack([_preprocess_image(image) for image in images]).astype(np.float32)
            output = self._session.run(None, {self._input_name: batch})[0]
            embeddings = _l2_normalize(_extract_cls_embedding(output, self.embedding_dimension))
        return SemanticEmbeddingResult(
            embeddings=embeddings.astype(np.float32),
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def load_semantic_provider(
    config: dict[str, object],
    providers: dict[str, SemanticEmbeddingProvider] | None = None,
) -> SemanticEmbeddingProvider:
    """按配置加载语义 embedding provider。"""
    provider_name = str(config.get("provider", "onnx_dinov2_small"))
    if providers is not None and provider_name in providers:
        return providers[provider_name]
    if provider_name != "onnx_dinov2_small":
        raise ValueError(f"unknown semantic provider: {provider_name}")
    model_path = config.get("model_path")
    return OnnxDinoV2SmallProvider(None if model_path is None else str(model_path))


def _resolve_model_path(model_path: str | Path | None, model_id: str) -> Path:
    """解析本地模型路径，未提供时从 Hugging Face Hub 下载。"""
    if model_path is not None:
        path = Path(model_path)
        if not path.exists():
            raise ValueError(f"model_path does not exist: {path}")
        return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SemanticDependencyError(
            "semantic optional dependencies are required; install image-gallery[semantic]"
        ) from exc
    return Path(hf_hub_download(repo_id=model_id, filename="onnx/model.onnx"))


def _preprocess_image(image: Image.Image) -> NDArray[np.float32]:
    """按 DINOv2 常用 ImageNet 归一化预处理图片。"""
    resized = image.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((array - mean) / std, (2, 0, 1))


def _extract_cls_embedding(output: NDArray[np.float32], dimension: int) -> NDArray[np.float32]:
    """从 ONNX 输出中提取 cls token embedding。"""
    array = np.asarray(output, dtype=np.float32)
    embeddings = array[:, 0, :] if array.ndim == 3 else array
    if embeddings.ndim != 2 or embeddings.shape[1] != dimension:
        raise ValueError(f"expected embedding dimension {dimension}, got shape {embeddings.shape}")
    return embeddings


def _l2_normalize(embeddings: NDArray[np.float32]) -> NDArray[np.float32]:
    """对 embedding 做 L2 归一化。"""
    norms: NDArray[np.float32] = np.linalg.norm(embeddings, axis=1, keepdims=True)
    if np.any(norms <= 0) or not np.isfinite(norms).all():
        raise ValueError("embedding contains zero or non-finite norm")
    return np.asarray(embeddings / norms, dtype=np.float32)
