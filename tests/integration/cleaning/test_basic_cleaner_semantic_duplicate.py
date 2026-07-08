import json
from pathlib import Path

import numpy as np
import pandas as pd
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


def test_basic_cleaner_runs_semantic_duplicate_with_injected_provider(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    near = tmp_path / "near.png"
    far = tmp_path / "far.png"
    _write_image(first, (255, 0, 0))
    _write_image(near, (250, 5, 5))
    _write_image(far, (0, 255, 0))
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["first", "near", "far"],
                "image_uri": [str(first), str(near), str(far)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner(
        [
            {
                "duplicate.semantic_duplicate_check": {
                    "threshold": 0.9,
                    "action": "drop",
                    "provider": "deterministic",
                }
            }
        ],
        semantic_providers={"deterministic": DeterministicSemanticProvider()},
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    full = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert full.loc["first", "semantic_duplicate_action"] == "keep"
    assert full.loc["near", "semantic_duplicate_action"] == "drop"
    assert full.loc["far", "semantic_duplicate_action"] == "keep"

    run_dir = next((tmp_path / "cleaning").iterdir())
    parameter_table = pd.read_parquet(run_dir / "parameter_table.parquet")
    assert "semantic_embedding_ref" in parameter_table.columns
    assert "semantic_duplicate_group_id" in parameter_table.columns
    assert (run_dir / "artifacts" / "semantic_embeddings" / "embeddings.npy").exists()
    assert (run_dir / "artifacts" / "semantic_index" / "faiss.index").exists()
    assert (run_dir / "relations" / "semantic_duplicate_pairs.parquet").exists()

    state_text = (run_dir / "state.json").read_text(encoding="utf-8")
    json.loads(state_text)
    assert "DeterministicSemanticProvider" not in state_text
