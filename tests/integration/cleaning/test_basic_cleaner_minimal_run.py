from pathlib import Path

import pandas as pd

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class IntegrationBackend(BackendAdapter):
    name = "integration_backend"

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        return BackendResult(
            parameter_updates=pd.DataFrame({"image_id": parameter_table["image_id"], "score": [1.0]}),
            relation_updates={},
            artifact_refs={},
        )


def test_basic_cleaner_minimal_run_writes_stage3_outputs(tmp_path: Path) -> None:
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": ["platform://local/a.jpg"]}),
        str(tmp_path / "raw.parquet"),
    )
    registry = OperatorRegistry()
    registry.register_backend(IntegrationBackend())
    registry.register_operator(
        OperatorSpec(
            name="quality.integration_check",
            category="quality",
            backend_name="integration_backend",
            parameter_columns=["score"],
            evaluation_columns=["integration_action", "integration_reason"],
            default_config={"action": "review"},
            action_column="integration_action",
            reason_column="integration_reason",
            evaluator=lambda parameter_table, config: pd.DataFrame(
                {
                    "image_id": parameter_table["image_id"],
                    "integration_action": config["action"],
                    "integration_reason": "integration",
                }
            ),
        )
    )

    cleaner = BasicCleaner([{"quality.integration_check": {}}], registry=registry)
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    assert cleaner.preview().review_count == 1
    assert cleaner.export("review", str(tmp_path / "review.parquet")).count() == 1
