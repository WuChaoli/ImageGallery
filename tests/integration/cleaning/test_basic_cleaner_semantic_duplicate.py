import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider, SemanticEmbeddingResult


class DeterministicSemanticProvider(SemanticEmbeddingProvider):
    """集成测试用固定向量 provider。"""

    provider_name = "deterministic"
    provider_version = "1"
    model_id = "deterministic"
    model_path = ""
    base_model = "deterministic"
    embedding_dimension = 3
    embedding_source = "test"
    normalized = True

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        embeddings = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.99, 0.01, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )[: len(images)]
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
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


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (16, 16), color=color).save(path)


def _build_semantic_dataset(tmp_path: Path) -> Dataset:
    first = tmp_path / "first.png"
    near = tmp_path / "near.png"
    far = tmp_path / "far.png"
    _write_image(first, (255, 0, 0))
    _write_image(near, (250, 5, 5))
    _write_image(far, (0, 255, 0))
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["first", "near", "far"],
                "image_uri": [str(first), str(near), str(far)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def _build_semantic_execution(tmp_path: Path):
    return BasicCleaner(
        [
            {
                "semantic_duplicate": {
                    "threshold": 0.9,
                    "action": "drop",
                    "provider": "deterministic",
                }
            }
        ],
        semantic_providers={"deterministic": DeterministicSemanticProvider()},
    ).compile()


def test_basic_cleaner_runs_semantic_duplicate_with_injected_provider(tmp_path: Path) -> None:
    dataset = _build_semantic_dataset(tmp_path)
    execution = _build_semantic_execution(tmp_path)
    result = execution.run(dataset)

    full = result.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert full.loc["first", "semantic_duplicate_action"] == "keep"
    assert full.loc["near", "semantic_duplicate_action"] == "drop"
    assert full.loc["far", "semantic_duplicate_action"] == "keep"

    run_dir = result._run_dir()
    parameter_table = pd.read_parquet(run_dir / "tables" / "parameter_table.parquet")
    assert "semantic_embedding_ref" in parameter_table.columns
    assert "semantic_duplicate_group_id" in parameter_table.columns
    assert (run_dir / "artifacts" / "semantic_embeddings" / "embeddings.npy").exists()
    assert (run_dir / "artifacts" / "semantic_embeddings" / "manifest.json").exists()
    assert (run_dir / "artifacts" / "semantic_index" / "faiss.index").exists()
    assert (run_dir / "artifacts" / "semantic_index" / "manifest.json").exists()
    assert (run_dir / "relations" / "semantic_duplicate_pairs.parquet").exists()
    assert (run_dir / "relations" / "semantic_duplicate_pairs.parquet.manifest.json").exists()

    state_text = (run_dir / "state.json").read_text(encoding="utf-8")
    json.loads(state_text)
    assert "DeterministicSemanticProvider" not in state_text


def test_resume_rejects_missing_semantic_embedding_manifest(tmp_path: Path) -> None:
    dataset = _build_semantic_dataset(tmp_path)
    execution = _build_semantic_execution(tmp_path)
    result = execution.run(dataset)
    run_dir = result._run_dir()
    (run_dir / "artifacts" / "semantic_embeddings" / "manifest.json").unlink()

    with pytest.raises(FileNotFoundError, match="artifact manifest missing"):
        execution.resume(dataset=dataset, run_id=result.run_id)


def test_rerun_rejects_semantic_index_manifest_without_config_hash(tmp_path: Path) -> None:
    dataset = _build_semantic_dataset(tmp_path)
    execution = _build_semantic_execution(tmp_path)
    result = execution.run(dataset)
    run_dir = result._run_dir()
    manifest_path = run_dir / "artifacts" / "semantic_index" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.pop("config_hash", None)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="artifact manifest config hash"):
        execution.rerun(
            result,
            operators=[
                {
                    "semantic_duplicate": {
                        "threshold": 0.9,
                        "action": "drop",
                        "provider": "deterministic",
                    }
                }
            ],
        )
