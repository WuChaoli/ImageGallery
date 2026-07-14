import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from PIL import Image

from image_gallery.operators.computers.base import (
    ExecutionMode,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
    ParameterStageSpec,
)
from image_gallery.operators.semantic_provider import (
    SemanticEmbeddingProvider,
    SemanticEmbeddingResult,
    load_semantic_provider,
)

SEMANTIC_EMBEDDING_REF = "semantic_embedding_ref"
SEMANTIC_INDEX_ARTIFACT = "semantic_index"


class SemanticEmbeddingComputer(ParameterComputer):
    """生成语义 embedding artifact，并在参数表中写入引用。"""

    name = "semantic_embedding_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({SEMANTIC_EMBEDDING_REF})

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
        embedding_result, embeddings = _embed_in_batches(
            provider,
            valid_images,
            _as_int(request.config.get("batch_size", 32)),
        )

        _write_embeddings(artifact_dir, embeddings, valid_image_ids)
        _write_embedding_manifest(artifact_dir, embedding_result, request.config_hash, len(valid_image_ids))

        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            if item.error is None and item.image is not None:
                rows.append({"image_id": item.image_id, SEMANTIC_EMBEDDING_REF: str(artifact_dir)})
            else:
                rows.append({"image_id": item.image_id, SEMANTIC_EMBEDDING_REF: ""})

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={"semantic_embeddings": str(artifact_dir)},
            parameter_manifest={
                SEMANTIC_EMBEDDING_REF: {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "artifact_ref": str(artifact_dir),
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


def _embed_in_batches(
    provider: SemanticEmbeddingProvider,
    images: list[Image.Image],
    batch_size: int,
) -> tuple[SemanticEmbeddingResult, NDArray[np.float32]]:
    """按配置批量调用 provider，避免一次性推理过多图片。"""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    results: list[NDArray[np.float32]] = []
    last_result: SemanticEmbeddingResult | None = None
    for start in range(0, len(images), batch_size):
        batch = images[start : start + batch_size]
        batch_result = provider.embed_images(batch)
        results.append(_validate_embeddings(batch_result, len(batch)))
        last_result = batch_result

    if last_result is None:
        empty_result = provider.embed_images([])
        return empty_result, _validate_embeddings(empty_result, 0)
    return last_result, np.vstack(results).astype(np.float32)


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


@dataclass(frozen=True)
class _EmbeddingArtifact:
    """已落盘语义向量 artifact 的内存表示。"""

    image_ids: list[str]
    embeddings: NDArray[np.float32]
    dimension: int


@dataclass(frozen=True)
class _SemanticPair:
    """语义重复 relation 的内部行。"""

    source_image_id: str
    target_image_id: str
    score: float
    group_id: str


class SemanticDuplicateGroupComputer(ParameterComputer):
    """基于语义 embedding 和 Faiss index 生成语义重复组。"""

    name = "semantic_duplicate_group_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset(
        {
            "semantic_duplicate_group_id",
            "semantic_duplicate_count",
            "semantic_duplicate_score",
            "semantic_duplicate_nearest_image_id",
        }
    )
    required_parameters = frozenset({SEMANTIC_EMBEDDING_REF})
    stages = (
        ParameterStageSpec(
            name="read_embeddings",
            required_artifacts=frozenset({"semantic_embeddings"}),
            artifact_contract="semantic_embeddings",
        ),
        ParameterStageSpec(
            name="build_index",
            required_artifacts=frozenset({"semantic_embeddings"}),
            produced_artifacts=frozenset({SEMANTIC_INDEX_ARTIFACT}),
            artifact_contract="semantic_index",
        ),
        ParameterStageSpec(
            name="find_pairs",
            required_artifacts=frozenset({SEMANTIC_INDEX_ARTIFACT}),
            artifact_contract="semantic_pairs",
        ),
        ParameterStageSpec(
            name="write_relations",
            required_artifacts=frozenset({SEMANTIC_INDEX_ARTIFACT}),
            produced_relations=frozenset({"semantic_duplicate_pairs"}),
            artifact_contract="semantic_duplicate_pairs",
        ),
    )

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """读取 embedding artifact，构建 Faiss index，并生成语义重复关系。"""
        threshold = _as_float(request.config.get("threshold", 0.92))
        index_type = str(request.config.get("index", "faiss_flat_ip"))
        if index_type != "faiss_flat_ip":
            raise ValueError(f"unsupported semantic index: {index_type}")

        frame = request.parameter_table[["image_id", SEMANTIC_EMBEDDING_REF]].copy()
        image_ids = frame["image_id"].astype(str).tolist()
        embedding_ref = _first_non_empty(cast(pd.Series, frame[SEMANTIC_EMBEDDING_REF]).fillna("").astype(str).tolist())
        if embedding_ref is None:
            return ParameterResult(
                parameter_updates=_empty_semantic_updates(image_ids),
                relation_updates={"semantic_duplicate_pairs": _semantic_relation_frame([])},
                artifact_refs={},
                parameter_manifest=_semantic_group_manifest(self, request.config_hash, threshold, ""),
            )

        embedding_artifact = _read_embedding_artifact(Path(embedding_ref))
        _validate_embedding_array(embedding_artifact.embeddings, embedding_artifact.dimension)
        index_path = request.artifacts_dir / SEMANTIC_INDEX_ARTIFACT / "faiss.index"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        _write_faiss_index(embedding_artifact.embeddings, index_path)
        _write_index_manifest(
            index_path.parent,
            threshold=threshold,
            source_embedding_ref=embedding_ref,
            image_count=len(embedding_artifact.image_ids),
            config_hash=request.config_hash,
        )
        updates, pairs = _build_semantic_groups(image_ids, embedding_artifact, threshold)

        return ParameterResult(
            parameter_updates=updates,
            relation_updates={
                "semantic_duplicate_pairs": _semantic_relation_frame(pairs, artifact_ref=str(index_path))
            },
            artifact_refs={SEMANTIC_INDEX_ARTIFACT: str(index_path)},
            parameter_manifest=_semantic_group_manifest(self, request.config_hash, threshold, str(index_path)),
        )


def _read_embedding_artifact(path: Path) -> _EmbeddingArtifact:
    """读取 embedding artifact。"""
    embeddings = np.load(path / "embeddings.npy").astype(np.float32)
    image_ids = pd.read_parquet(path / "image_ids.parquet")["image_id"].astype(str).tolist()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    return _EmbeddingArtifact(
        image_ids=image_ids,
        embeddings=embeddings,
        dimension=int(manifest["embedding_dimension"]),
    )


def _validate_embedding_array(embeddings: NDArray[np.float32], dimension: int) -> None:
    """校验已落盘 embedding 数组。"""
    if embeddings.ndim != 2:
        raise ValueError(f"embedding array must be 2-dimensional, got {embeddings.ndim}")
    if embeddings.shape[1] != dimension:
        raise ValueError(f"expected embedding dimension {dimension}, got {embeddings.shape[1]}")
    if not np.isfinite(embeddings).all():
        raise ValueError("embedding array contains non-finite values")


def _write_faiss_index(embeddings: NDArray[np.float32], path: Path) -> None:
    """写出 Faiss FlatIP index。"""
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is required for semantic duplicate index; install image-gallery[semantic]"
        ) from exc
    index = faiss.IndexFlatIP(int(embeddings.shape[1]))
    index.add(np.ascontiguousarray(embeddings.astype(np.float32)))
    faiss.write_index(index, str(path))


def _write_index_manifest(
    artifact_dir: Path,
    *,
    threshold: float,
    source_embedding_ref: str,
    image_count: int,
    config_hash: str,
) -> None:
    """写出 Faiss index manifest。"""
    manifest = {
        "artifact_schema_version": 1,
        "index_type": "faiss_flat_ip",
        "metric": "cosine",
        "threshold": threshold,
        "source_embedding_ref": source_embedding_ref,
        "image_count": image_count,
        "config_hash": config_hash,
    }
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_semantic_groups(
    all_image_ids: list[str],
    artifact: _EmbeddingArtifact,
    threshold: float,
) -> tuple[pd.DataFrame, list[_SemanticPair]]:
    """按 parameter_table 顺序构造 keeper-first 语义重复组。"""
    embedding_by_id = {image_id: artifact.embeddings[index] for index, image_id in enumerate(artifact.image_ids)}
    groups: list[tuple[str, NDArray[np.float32], list[str]]] = []
    assignments: dict[str, tuple[str, int, float | None, str]] = {}
    pairs: list[_SemanticPair] = []

    for image_id in all_image_ids:
        embedding = embedding_by_id.get(image_id)
        if embedding is None:
            assignments[image_id] = ("", 1, None, "")
            continue

        best_index: int | None = None
        best_score = -1.0
        for index, (_keeper_id, keeper_embedding, _members) in enumerate(groups):
            score = float(np.dot(embedding, keeper_embedding))
            if score >= threshold and score > best_score:
                best_index = index
                best_score = score

        if best_index is None:
            groups.append((image_id, embedding, [image_id]))
            assignments[image_id] = ("", 1, None, "")
            continue

        keeper_id, _keeper_embedding, members = groups[best_index]
        members.append(image_id)
        group_id = f"semantic-{keeper_id}"
        pairs.append(_SemanticPair(keeper_id, image_id, best_score, group_id))
        assignments[image_id] = (group_id, len(members), best_score, keeper_id)
        for member_id in members:
            member_score: float | None = 1.0 if member_id == keeper_id else assignments[member_id][2]
            nearest = "" if member_id == keeper_id else keeper_id
            assignments[member_id] = (group_id, len(members), member_score, nearest)

    rows = []
    for image_id in all_image_ids:
        group_id, count, assigned_score, nearest = assignments[image_id]
        if count <= 1:
            group_id = ""
            assigned_score = None
            nearest = ""
        rows.append(
            {
                "image_id": image_id,
                "semantic_duplicate_group_id": group_id,
                "semantic_duplicate_count": count,
                "semantic_duplicate_score": pd.NA if assigned_score is None else float(assigned_score),
                "semantic_duplicate_nearest_image_id": nearest,
            }
        )
    return pd.DataFrame(rows), pairs


def _semantic_relation_frame(pairs: list[_SemanticPair], artifact_ref: str = "") -> pd.DataFrame:
    """构造语义重复 pair relation。"""
    created_at = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame(
        [
            {
                "relation_type": "semantic_duplicate",
                "source_image_id": pair.source_image_id,
                "target_image_id": pair.target_image_id,
                "score": pair.score,
                "group_id": pair.group_id,
                "parameter_name": "semantic_duplicate_group_id",
                "computer_name": "semantic_duplicate_group_computer",
                "artifact_ref": artifact_ref,
                "created_at": created_at,
            }
            for pair in pairs
        ],
        columns=[
            "relation_type",
            "source_image_id",
            "target_image_id",
            "score",
            "group_id",
            "parameter_name",
            "computer_name",
            "artifact_ref",
            "created_at",
        ],
    )


def _empty_semantic_updates(image_ids: list[str]) -> pd.DataFrame:
    """构造没有有效 embedding 时的空分组参数。"""
    return pd.DataFrame(
        {
            "image_id": image_ids,
            "semantic_duplicate_group_id": ["" for _ in image_ids],
            "semantic_duplicate_count": [1 for _ in image_ids],
            "semantic_duplicate_score": [pd.NA for _ in image_ids],
            "semantic_duplicate_nearest_image_id": ["" for _ in image_ids],
        }
    )


def _semantic_group_manifest(
    computer: SemanticDuplicateGroupComputer,
    config_hash: str,
    threshold: float,
    index_ref: str,
) -> dict[str, dict[str, object]]:
    """构造语义分组参数 manifest。"""
    return {
        parameter: {
            "computer": computer.name,
            "execution_mode": computer.execution_mode.value,
            "config_hash": config_hash,
            "depends_on": [SEMANTIC_EMBEDDING_REF],
            "threshold": threshold,
            "artifact_ref": index_ref,
        }
        for parameter in sorted(computer.produced_parameters)
    }


def _first_non_empty(values: list[str]) -> str | None:
    """返回第一个非空字符串。"""
    for value in values:
        if value:
            return value
    return None


def _as_float(value: object) -> float:
    """把配置值转换为 float。"""
    if isinstance(value, (str, bytes, int, float)):
        return float(value)
    raise TypeError(f"expected float-compatible config value, got {type(value).__name__}")


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")
