from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.errors import CleanerStateError
from image_gallery.dataset import Dataset
from image_gallery.operators.computers.base import (
    ExecutionMode,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class CountingComputer(ParameterComputer):
    name = "counting_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"demo_score"})

    def __init__(self) -> None:
        self.calls: list[tuple[set[str], int]] = []

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is not None
        self.calls.append((set(request.requested_parameters), len(request.image_batch.items)))
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "demo_score": [0.9, 0.2],
                }
            ),
            relation_updates={},
            artifact_refs={"counting_computer": str(Path(request.artifacts_dir) / "counting")},
            parameter_manifest={
                "demo_score": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
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


class CountingReadDataset(Dataset):
    def __init__(self, dataset_path: str, image_bytes: bytes) -> None:
        super().__init__(dataset_path=dataset_path)
        self.image_bytes = image_bytes
        self.read_calls: list[str] = []

    def read_image_bytes(self, image_uri: str) -> bytes:
        self.read_calls.append(image_uri)
        return self.image_bytes


def _registry(computer: CountingComputer) -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(computer)
    registry.register_operator(
        OperatorSpec(
            name="quality.drop_check",
            category="quality",
            required_parameters=["demo_score"],
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
            required_parameters=["demo_score"],
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


def test_basic_cleaner_runs_shared_parameter_computer_and_exposes_results(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner(
        [
            {"quality.drop_check": {}},
            {"quality.review_check": {}},
        ],
        registry=_registry(computer),
    )

    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    assert computer.calls == [({"demo_score"}, 2)]
    run_dir = next((tmp_path / "cleaning").iterdir())
    assert (run_dir / "parameter_manifest.json").exists()
    assert pd.read_json(run_dir / "parameter_manifest.json", typ="series").to_dict()["demo_score"] == {
        "computer": "counting_computer",
        "config_hash": "default",
        "execution_mode": "per_image",
    }
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


def test_basic_cleaner_writes_relation_outputs_and_state_paths(tmp_path: Path) -> None:
    class RelationComputer(CountingComputer):
        name = "relation_computer"

        def compute(self, request: ParameterRequest) -> ParameterResult:
            base = super().compute(request)
            return ParameterResult(
                parameter_updates=base.parameter_updates,
                relation_updates={
                    "demo_pairs": pd.DataFrame(
                        {
                            "relation_type": ["demo"],
                            "source_image_id": ["img-1"],
                            "target_image_id": ["img-2"],
                            "score": [1.0],
                            "group_id": ["group-1"],
                            "parameter_name": ["demo_score"],
                            "computer_name": [self.name],
                            "artifact_ref": [""],
                            "created_at": ["2026-07-06T00:00:00Z"],
                        }
                    )
                },
                artifact_refs=base.artifact_refs,
                parameter_manifest=base.parameter_manifest,
            )

    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(RelationComputer()))
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    run_dir = next((tmp_path / "cleaning").iterdir())
    relation_path = run_dir / "relations" / "demo_pairs.parquet"
    assert relation_path.exists()

    state_payload = pd.read_json(run_dir / "state.json", typ="series").to_dict()
    assert state_payload["parameter_manifest_path"].endswith("parameter_manifest.json")
    assert state_payload["parameter_config_hashes"] == {"demo_score": "default"}
    assert state_payload["relation_paths"] == {"demo_pairs": str(relation_path)}
    assert state_payload["started_at"]
    assert state_payload["finished_at"]


def test_basic_cleaner_rejects_result_before_run() -> None:
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(CountingComputer()))

    with pytest.raises(CleanerStateError):
        cleaner.result("quality.drop_check")


def test_basic_cleaner_plan_auto_compiles_without_running_dataset(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner(
        [
            {"quality.drop_check": {}},
            {"quality.review_check": {}},
        ],
        registry=_registry(computer),
    )

    frame = cleaner.plan()

    assert frame["computer_name"].tolist() == ["counting_computer"]
    assert frame["execution_mode"].tolist() == ["per_image"]
    assert frame["requested_parameters"].tolist() == ["demo_score"]
    assert computer.calls == []
    assert not (tmp_path / "cleaning").exists()


def test_basic_cleaner_compile_returns_self_and_run_uses_cached_plan(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))

    assert cleaner.compile() is cleaner
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    assert computer.calls == [({"demo_score"}, 2)]


def test_basic_cleaner_config_invalidates_compiled_plan() -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))
    assert cleaner.plan()["requested_parameters"].tolist() == ["demo_score"]

    cleaner.config([{"quality.review_check": {}}])

    assert cleaner.plan()["computer_name"].tolist() == ["counting_computer"]


def test_basic_cleaner_config_marks_operator_stale_without_computer_call(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    cleaner.config([{"quality.drop_check": {"threshold": 0.95}}])

    assert computer.calls == [({"demo_score"}, 2)]
    assert cleaner.state().to_dict(orient="records")[0]["status"] == "stale"


def test_basic_cleaner_rerun_recomputes_evaluation_only(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    cleaner.rerun([{"quality.drop_check": {"threshold": 0.95}}])

    assert computer.calls == [({"demo_score"}, 2)]
    assert cleaner.preview().clean_count == 2
    assert cleaner.state().to_dict(orient="records")[0]["status"] == "completed"


def test_basic_cleaner_builds_shared_image_batch_with_one_byte_read_per_image(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    image_buffer = BytesIO()
    Image.new("RGB", (4, 3), color=(255, 0, 0)).save(image_buffer, format="PNG")
    image_path.write_bytes(image_buffer.getvalue())
    raw_path = tmp_path / "raw.parquet"
    pd.DataFrame(
        {
            "image_id": ["img-1"],
            "image_uri": [str(image_path)],
        }
    ).to_parquet(raw_path, index=False)
    dataset = CountingReadDataset(str(raw_path), image_path.read_bytes())
    cleaner = BasicCleaner([{"format.decode_check": {}}])
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    assert dataset.read_calls == [str(image_path)]
