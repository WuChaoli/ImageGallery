from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.errors import CleanerStateError
from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class CountingBackend(BackendAdapter):
    name = "counting_backend"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        self.calls.append([request.operator_name for request in requests])
        return BackendResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": parameter_table["image_id"],
                    "demo_score": [0.9, 0.2],
                }
            ),
            relation_updates={},
            artifact_refs={"counting_backend": str(Path(artifacts_dir) / "counting")},
        )


def _evaluate_drop(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    threshold = float(config["threshold"])
    action = str(config["action"])
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "drop_action": parameter_table["demo_score"].map(lambda value: action if value >= threshold else "keep"),
            "drop_reason": parameter_table["demo_score"].map(lambda value: "high score" if value >= threshold else ""),
        }
    )


def _evaluate_review(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    threshold = float(config["threshold"])
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "review_action": parameter_table["demo_score"].map(
                lambda value: "review" if value >= threshold else "keep"
            ),
            "review_reason": parameter_table["demo_score"].map(
                lambda value: "needs review" if value >= threshold else ""
            ),
        }
    )


def _registry(backend: CountingBackend) -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_backend(backend)
    registry.register_operator(
        OperatorSpec(
            name="quality.drop_check",
            category="quality",
            backend_name=backend.name,
            parameter_columns=["demo_score"],
            evaluation_columns=["drop_action", "drop_reason"],
            default_config={"threshold": 0.8, "action": "drop"},
            action_column="drop_action",
            reason_column="drop_reason",
            evaluator=_evaluate_drop,
        )
    )
    registry.register_operator(
        OperatorSpec(
            name="quality.review_check",
            category="quality",
            backend_name=backend.name,
            parameter_columns=["demo_score"],
            evaluation_columns=["review_action", "review_reason"],
            default_config={"threshold": 0.5},
            action_column="review_action",
            reason_column="review_reason",
            evaluator=_evaluate_review,
        )
    )
    return registry


def _dataset(tmp_path: Path) -> Dataset:
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": ["platform://local/a.jpg", "platform://local/b.jpg"],
                "source_uri": ["file:///a.jpg", "file:///b.jpg"],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_basic_cleaner_runs_grouped_backend_and_exposes_results(tmp_path: Path) -> None:
    backend = CountingBackend()
    cleaner = BasicCleaner(
        [
            {"quality.drop_check": {}},
            {"quality.review_check": {}},
        ],
        registry=_registry(backend),
    )

    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    assert backend.calls == [["quality.drop_check", "quality.review_check"]]
    assert cleaner.preview().dropped_count == 1
    assert cleaner.state()["operator_name"].tolist() == ["quality.drop_check", "quality.review_check"]
    assert cleaner.result("quality.drop_check").columns.tolist() == [
        "image_id",
        "image_uri",
        "drop_action",
        "drop_reason",
    ]
    assert cleaner.export("clean", str(tmp_path / "clean.parquet")).count() == 1
    assert (next((tmp_path / "cleaning").iterdir()) / "state.json").exists()


def test_basic_cleaner_rejects_result_before_run() -> None:
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(CountingBackend()))

    with pytest.raises(CleanerStateError):
        cleaner.result("quality.drop_check")


def test_basic_cleaner_config_marks_operator_stale_without_backend_call(tmp_path: Path) -> None:
    backend = CountingBackend()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(backend))
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    cleaner.config([{"quality.drop_check": {"threshold": 0.95}}])

    assert backend.calls == [["quality.drop_check"]]
    assert cleaner.state().to_dict(orient="records")[0]["status"] == "stale"


def test_basic_cleaner_rerun_recomputes_requested_operator(tmp_path: Path) -> None:
    backend = CountingBackend()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(backend))
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    cleaner.rerun([{"quality.drop_check": {"threshold": 0.95}}])

    assert backend.calls == [["quality.drop_check"]]
    assert cleaner.preview().clean_count == 2
    assert cleaner.state().to_dict(orient="records")[0]["status"] == "completed"
