from io import BytesIO
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.context import create_run_context
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.scheduler import ParameterScheduler
from image_gallery.cleaning.tables import CleaningTables, initialize_evaluation_table, initialize_parameter_table
from image_gallery.dataset import Dataset
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class CountingImageComputer(ParameterComputer):
    name = "counting_image_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"image_score"})

    def __init__(self) -> None:
        self.calls = 0

    def compute(self, request: ParameterRequest) -> ParameterResult:
        self.calls += 1
        assert request.image_batch is not None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "image_score": [1.0 for _ in request.image_batch.items],
                }
            ),
            relation_updates={},
            artifact_refs={"counting_image_computer": str(request.artifacts_dir / "image")},
            parameter_manifest={
                "image_score": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


class TableComputer(ParameterComputer):
    name = "table_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"table_score"})
    required_parameters = frozenset({"image_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "table_score": request.parameter_table["image_score"] + 1.0,
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "table_score": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["image_score"],
                }
            },
        )


class AggregateComputer(ParameterComputer):
    name = "aggregate_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"group_id"})
    required_parameters = frozenset({"table_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is None
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "group_id": ["g1"]}),
            relation_updates={
                "demo_pairs": pd.DataFrame(
                    {
                        "relation_type": ["demo"],
                        "source_image_id": ["img-1"],
                        "target_image_id": ["img-1"],
                        "score": [1.0],
                        "group_id": ["g1"],
                        "parameter_name": ["group_id"],
                        "computer_name": [self.name],
                        "artifact_ref": [""],
                        "created_at": ["2026-07-08T00:00:00Z"],
                    }
                )
            },
            artifact_refs={},
            parameter_manifest={
                "group_id": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["table_score"],
                }
            },
        )


class CountingReadDataset(Dataset):
    def __init__(self, dataset_path: str, image_bytes: bytes) -> None:
        super().__init__(dataset_path=dataset_path)
        self.image_bytes = image_bytes
        self.read_calls: list[str] = []

    def read_image_bytes(self, image_uri: str) -> bytes:
        self.read_calls.append(image_uri)
        return self.image_bytes


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "demo_action": "keep", "demo_reason": ""})


def _registry(image_computer: CountingImageComputer) -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(image_computer)
    registry.register_parameter_computer(TableComputer())
    registry.register_parameter_computer(AggregateComputer())
    registry.register_operator(
        OperatorSpec(
            name="demo.aggregate_check",
            category="demo",
            required_parameters=["group_id"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    return registry


def _dataset(tmp_path: Path) -> CountingReadDataset:
    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    raw_path = tmp_path / "raw.parquet"
    pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(tmp_path / "img.png")]}).to_parquet(raw_path, index=False)
    return CountingReadDataset(str(raw_path), image_bytes)


def test_scheduler_executes_plan_and_merges_outputs(tmp_path: Path) -> None:
    image_computer = CountingImageComputer()
    registry = _registry(image_computer)
    dataset = _dataset(tmp_path)
    context = create_run_context(
        dataset,
        "basic",
        parse_operator_configs([{"demo.aggregate_check": {}}]),
        tmp_path / "cleaning",
    )
    parameter_table = initialize_parameter_table(dataset)
    tables = CleaningTables(
        parameter_table=parameter_table,
        evaluation_table=initialize_evaluation_table(parameter_table),
        operator_outputs={},
        parameter_manifest={},
    )
    plan = CleaningRunPlanner(registry).compile(parse_operator_configs([{"demo.aggregate_check": {}}]))

    result = ParameterScheduler(registry).run(plan.parameter_plan, context, tables)

    assert image_computer.calls == 1
    assert dataset.read_calls == [str(tmp_path / "img.png")]
    assert result.tables.parameter_table["group_id"].tolist() == ["g1"]
    assert set(result.tables.parameter_manifest) == {"image_score", "table_score", "group_id"}
    assert result.artifact_paths == {"counting_image_computer": str(context.paths.artifacts_dir / "image")}
    assert result.relation_paths["demo_pairs"].endswith("relations/demo_pairs.parquet")
