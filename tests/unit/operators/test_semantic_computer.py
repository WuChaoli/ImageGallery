import json
from importlib.machinery import ModuleSpec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.semantic import SemanticDuplicateGroupComputer, SemanticEmbeddingComputer
from image_gallery.operators.semantic_provider import (
    SemanticDependencyError,
    SemanticEmbeddingProvider,
    SemanticEmbeddingResult,
)


class FakeSemanticProvider(SemanticEmbeddingProvider):
    """测试用语义 embedding provider。"""

    provider_name = "fake_provider"
    provider_version = "1"
    model_id = "fake-model"
    model_path = "/tmp/fake.onnx"
    base_model = "fake-base"
    embedding_dimension = 3
    embedding_source = "unit"
    normalized = True

    def __init__(self, embeddings: np.ndarray) -> None:
        self._embeddings = embeddings.astype(np.float32)
        self.batch_sizes: list[int] = []

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        self.batch_sizes.append(len(images))
        return SemanticEmbeddingResult(
            embeddings=self._embeddings[: len(images)],
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def _request(tmp_path: Path, provider_name: str = "fake") -> ParameterRequest:
    image = Image.new("RGB", (8, 8), color=(100, 120, 140))
    return ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": ["a", "b"], "image_uri": ["a.png", "b.png"]}),
        requested_parameters=frozenset({"semantic_embedding_ref"}),
        config={"provider": provider_name},
        config_hash="cfg",
        artifacts_dir=tmp_path / "artifacts",
        image_batch=ImageBatch(
            items=[
                ImageBatchItem("a", "a.png", {}, b"a", image, None),
                ImageBatchItem("b", "b.png", {}, b"b", None, "decode failed"),
            ]
        ),
    )


def _multi_image_request(tmp_path: Path, image_count: int, batch_size: int) -> ParameterRequest:
    image = Image.new("RGB", (8, 8), color=(100, 120, 140))
    return ParameterRequest(
        parameter_table=pd.DataFrame(
            {
                "image_id": [f"img-{index}" for index in range(image_count)],
                "image_uri": [f"img-{index}.png" for index in range(image_count)],
            }
        ),
        requested_parameters=frozenset({"semantic_embedding_ref"}),
        config={"provider": "fake", "batch_size": batch_size},
        config_hash="cfg",
        artifacts_dir=tmp_path / "artifacts",
        image_batch=ImageBatch(
            items=[
                ImageBatchItem(f"img-{index}", f"img-{index}.png", {}, b"img", image.copy(), None)
                for index in range(image_count)
            ]
        ),
    )


def test_semantic_embedding_computer_writes_artifact_and_refs(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))

    result = SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))

    artifact_dir = tmp_path / "artifacts" / "semantic_embeddings"
    assert np.load(artifact_dir / "embeddings.npy").tolist() == [[1.0, 0.0, 0.0]]
    assert pd.read_parquet(artifact_dir / "image_ids.parquet")["image_id"].tolist() == ["a"]
    manifest = json.loads((artifact_dir / "manifest.json").read_text())
    assert manifest["artifact_schema_version"] == 1
    assert manifest["embedding_dimension"] == 3
    assert manifest["image_count"] == 1
    assert manifest["config_hash"] == "cfg"
    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "a", "semantic_embedding_ref": str(artifact_dir)},
        {"image_id": "b", "semantic_embedding_ref": ""},
    ]
    assert result.artifact_refs == {"semantic_embeddings": str(artifact_dir)}


def test_semantic_embedding_computer_rejects_non_finite_vectors(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[float("nan"), 0.0, 0.0]], dtype=np.float32))

    with pytest.raises(ValueError, match="non-finite"):
        SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))


def test_semantic_embedding_computer_batches_provider_calls(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )
    )

    result = SemanticEmbeddingComputer({"fake": provider}).compute(_multi_image_request(tmp_path, 5, 2))

    assert provider.batch_sizes == [2, 2, 1]
    artifact_dir = tmp_path / "artifacts" / "semantic_embeddings"
    assert np.load(artifact_dir / "embeddings.npy").shape == (5, 3)
    assert result.parameter_updates["semantic_embedding_ref"].ne("").all()


def test_semantic_embedding_before_run_check_reports_missing_onnxruntime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_find_spec(name: str) -> ModuleSpec | None:
        if name == "onnxruntime":
            return None
        return ModuleSpec(name, loader=None)

    monkeypatch.setattr("image_gallery.operators.computers.semantic.find_spec", fake_find_spec)

    with pytest.raises(SemanticDependencyError, match="install image-gallery\\[semantic\\]"):
        SemanticEmbeddingComputer().before_run_check()


def test_semantic_embedding_before_run_check_passes_when_dependencies_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_find_spec(name: str) -> ModuleSpec:
        return ModuleSpec(name, loader=None)

    monkeypatch.setattr("image_gallery.operators.computers.semantic.find_spec", fake_find_spec)

    SemanticEmbeddingComputer().before_run_check()


def test_semantic_embedding_before_run_check_reports_missing_model_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.onnx"

    with pytest.raises(FileNotFoundError, match="model_path does not exist"):
        SemanticEmbeddingComputer({"fake": FakeSemanticProvider(np.empty((0, 3), dtype=np.float32))}).before_run_check(
            {"model_path": str(missing_path)}
        )


def test_semantic_duplicate_before_run_check_reports_missing_onnxruntime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_find_spec(name: str) -> ModuleSpec | None:
        if name == "onnxruntime":
            return None
        return ModuleSpec(name, loader=None)

    monkeypatch.setattr("image_gallery.operators.computers.semantic.find_spec", fake_find_spec)

    with pytest.raises(SemanticDependencyError, match="onnxruntime"):
        SemanticDuplicateGroupComputer().before_run_check()


def _write_embedding_artifact(tmp_path: Path) -> str:
    artifact_dir = tmp_path / "artifacts" / "semantic_embeddings"
    artifact_dir.mkdir(parents=True)
    np.save(
        artifact_dir / "embeddings.npy",
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.99, 0.01, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        ),
    )
    pd.DataFrame({"image_id": ["keeper", "near", "far"]}).to_parquet(artifact_dir / "image_ids.parquet", index=False)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": 1,
                "provider_name": "fake",
                "provider_version": "1",
                "model_id": "fake",
                "model_path": "/tmp/fake.onnx",
                "base_model": "fake",
                "embedding_dimension": 3,
                "normalized": True,
                "embedding_source": "unit",
                "image_count": 3,
                "config_hash": "cfg",
            }
        ),
        encoding="utf-8",
    )
    return str(artifact_dir)


def test_semantic_duplicate_group_computer_groups_vectors_and_writes_relations(tmp_path: Path) -> None:
    embedding_ref = _write_embedding_artifact(tmp_path)
    request = ParameterRequest(
        parameter_table=pd.DataFrame(
            {
                "image_id": ["keeper", "near", "far"],
                "semantic_embedding_ref": [embedding_ref, embedding_ref, embedding_ref],
            }
        ),
        requested_parameters=frozenset(
            {
                "semantic_duplicate_group_id",
                "semantic_duplicate_count",
                "semantic_duplicate_score",
                "semantic_duplicate_nearest_image_id",
            }
        ),
        config={"threshold": 0.9, "index": "faiss_flat_ip"},
        config_hash="cfg",
        artifacts_dir=tmp_path / "artifacts",
    )

    result = SemanticDuplicateGroupComputer().compute(request)

    rows = result.parameter_updates.set_index("image_id")
    assert rows.loc["keeper", "semantic_duplicate_group_id"].startswith("semantic-")
    assert rows.loc["keeper", "semantic_duplicate_count"] == 2
    assert rows.loc["near", "semantic_duplicate_count"] == 2
    assert rows.loc["near", "semantic_duplicate_nearest_image_id"] == "keeper"
    assert rows.loc["far", "semantic_duplicate_group_id"] == ""
    pairs = result.relation_updates["semantic_duplicate_pairs"]
    assert pairs[["relation_type", "source_image_id", "target_image_id", "parameter_name"]].to_dict(
        orient="records"
    ) == [
        {
            "relation_type": "semantic_duplicate",
            "source_image_id": "keeper",
            "target_image_id": "near",
            "parameter_name": "semantic_duplicate_group_id",
        }
    ]
    assert Path(result.artifact_refs["semantic_index"]).exists()


def test_semantic_duplicate_group_computer_keeps_all_rows_when_no_valid_embedding(tmp_path: Path) -> None:
    request = ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": ["bad"], "semantic_embedding_ref": [""]}),
        requested_parameters=frozenset({"semantic_duplicate_group_id"}),
        config={"threshold": 0.9, "index": "faiss_flat_ip"},
        config_hash="cfg",
        artifacts_dir=tmp_path / "artifacts",
    )

    result = SemanticDuplicateGroupComputer().compute(request)

    row = result.parameter_updates.iloc[0]
    assert row["semantic_duplicate_group_id"] == ""
    assert row["semantic_duplicate_count"] == 1
    assert pd.isna(row["semantic_duplicate_score"])
    assert result.relation_updates["semantic_duplicate_pairs"].empty
