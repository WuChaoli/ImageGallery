import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from PIL import Image

from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.semantic_provider import (
    SemanticEmbeddingProvider,
    SemanticEmbeddingResult,
    load_semantic_provider,
)


class SemanticEmbeddingComputer(ParameterComputer):
    """生成语义 embedding artifact，并在参数表中写入引用。"""

    name = "semantic_embedding_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"semantic_embedding_ref"})

    def __init__(self, providers: dict[str, SemanticEmbeddingProvider] | None = None) -> None:
        self._providers = providers or {}

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """提取有效图片的语义 embedding 并产出引用参数。"""
        if request.image_batch is None:
            raise ValueError("SemanticEmbeddingComputer requires image_batch")

        valid_images: list[Image.Image] = []
        valid_image_ids: list[str] = []
        for item in request.image_batch.items:
            if item.error is None and item.image is not None:
                valid_images.append(item.image)
                valid_image_ids.append(item.image_id)

        artifact_dir = request.artifacts_dir / "semantic_embeddings"

        provider = load_semantic_provider(request.config, self._providers)
        embedding_result = provider.embed_images(valid_images)
        embeddings = _validate_embeddings(embedding_result, len(valid_images))

        _write_embeddings(artifact_dir, embeddings, valid_image_ids)
        _write_embedding_manifest(artifact_dir, embedding_result, request.config_hash, len(valid_image_ids))

        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            if item.error is None and item.image is not None:
                rows.append({"image_id": item.image_id, "semantic_embedding_ref": str(artifact_dir)})
            else:
                rows.append({"image_id": item.image_id, "semantic_embedding_ref": ""})

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={"semantic_embeddings": str(artifact_dir)},
            parameter_manifest={
                "semantic_embedding_ref": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def _write_embeddings(
    artifact_dir: Path,
    embeddings: NDArray[np.float32],
    image_ids: list[str],
) -> None:
    """写入 embedding 与 image_id 列表，保持成功图片与行一一对应。"""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    np.save(artifact_dir / "embeddings.npy", embeddings)
    pd.DataFrame({"image_id": image_ids}).to_parquet(artifact_dir / "image_ids.parquet", index=False)


def _validate_embeddings(
    result: SemanticEmbeddingResult,
    expected_count: int,
) -> NDArray[np.float32]:
    """校验并标准化 embedding 结果，避免后续写入非有限值。"""
    embeddings = np.asarray(result.embeddings, dtype=np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] != expected_count:
        raise ValueError(f"embedding shape mismatch: expected {expected_count} rows, got {embeddings.shape}")
    if not np.all(np.isfinite(embeddings)):
        raise ValueError("embedding contains non-finite values")
    return embeddings


def _write_embedding_manifest(
    artifact_dir: Path,
    result: SemanticEmbeddingResult,
    config_hash: str,
    image_count: int,
) -> None:
    """写入语义 embedding 模型与参数快照。"""
    manifest = {
        "artifact_schema_version": 1,
        "provider_name": result.provider_name,
        "provider_version": result.provider_version,
        "model_id": result.model_id,
        "model_path": result.model_path,
        "base_model": result.base_model,
        "embedding_dimension": result.embedding_dimension,
        "embedding_source": result.embedding_source,
        "normalized": result.normalized,
        "image_count": image_count,
        "config_hash": config_hash,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
