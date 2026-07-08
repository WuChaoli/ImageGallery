import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.semantic import SemanticEmbeddingComputer
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider, SemanticEmbeddingResult


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

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
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


def test_semantic_embedding_computer_writes_artifact_and_refs(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))

    result = SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))

    artifact_dir = tmp_path / "artifacts" / "semantic_embeddings"
    assert np.load(artifact_dir / "embeddings.npy").tolist() == [[1.0, 0.0, 0.0]]
    assert pd.read_parquet(artifact_dir / "image_ids.parquet")["image_id"].tolist() == ["a"]
    assert json.loads((artifact_dir / "manifest.json").read_text())["embedding_dimension"] == 3
    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "a", "semantic_embedding_ref": str(artifact_dir)},
        {"image_id": "b", "semantic_embedding_ref": ""},
    ]
    assert result.artifact_refs == {"semantic_embeddings": str(artifact_dir)}


def test_semantic_embedding_computer_rejects_non_finite_vectors(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[float("nan"), 0.0, 0.0]], dtype=np.float32))

    with pytest.raises(ValueError, match="non-finite"):
        SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))
