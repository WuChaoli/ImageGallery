import json
import sqlite3
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning.context import build_run_paths
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.runtime import CleaningRuntime, RunOptions
from image_gallery.cleaning.state import JsonRunStateStore
from image_gallery.cleaning.tables import read_tables
from image_gallery.dataset import Dataset
from image_gallery.operators.computers.base import (
    ExecutionMode,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec, OperatorSpec


class TrackingComputer(ParameterComputer):
    """记录参数阶段执行次数的测试 computer。"""

    name = "tracking_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"tracked_value"})
    call_count: ClassVar[int] = 0

    def compute(self, request: ParameterRequest) -> ParameterResult:
        type(self).call_count += 1
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "tracked_value": [1] * len(request.parameter_table),
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "tracked_value": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


class ControlledParameterComputer(ParameterComputer):
    """允许测试在参数阶段稳定触发成功或失败。"""

    name = "controlled_parameter_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"tracked_value"})

    def __init__(self) -> None:
        self.fail = False
        self.call_count = 0

    def compute(self, request: ParameterRequest) -> ParameterResult:
        self.call_count += 1
        if self.fail:
            raise RuntimeError("controlled parameter failure")
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "tracked_value": [1] * len(request.parameter_table),
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "tracked_value": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


class ControlledEvaluator:
    """允许测试在 evaluation 边界稳定触发成功或失败。"""

    def __init__(self, output_prefix: str = "tracked") -> None:
        self.output_prefix = output_prefix
        self.fail = False
        self.call_count = 0

    @property
    def action_column(self) -> str:
        return f"{self.output_prefix}_action"

    @property
    def reason_column(self) -> str:
        return f"{self.output_prefix}_reason"

    def __call__(self, frame: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
        del config
        self.call_count += 1
        if self.fail:
            raise RuntimeError("controlled evaluation failure")
        return pd.DataFrame(
            {
                "image_id": frame["image_id"],
                self.action_column: ["keep"] * len(frame),
                self.reason_column: [""] * len(frame),
            }
        )


def _write_dataset(tmp_path: Path) -> Dataset:
    image_path = tmp_path / "image.png"
    with Image.new("RGB", (2, 2), color=(255, 0, 0)) as image:
        image.save(image_path)
    return Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )


def _build_runtime_inputs(
    evaluator: ControlledEvaluator,
    parameter_computer: ParameterComputer | None = None,
) -> tuple[OperatorRegistry, list[ConfiguredOperatorSpec], CleaningStateGraph]:
    registry = OperatorRegistry()
    registry.register_parameter_computer(parameter_computer or TrackingComputer())
    operator = OperatorSpec(
        name="test.tracked",
        category="test",
        required_parameters=["tracked_value"],
        evaluation_columns=[evaluator.action_column, evaluator.reason_column],
        default_config={},
        action_column=evaluator.action_column,
        reason_column=evaluator.reason_column,
        evaluator=evaluator,
    )
    registry.register_operator(operator)
    configured = [ConfiguredOperatorSpec.from_spec(operator, {}, source="test")]
    return registry, configured, CleaningStateGraph.compile(configured, registry)


def _build_two_evaluator_inputs(
    first: ControlledEvaluator,
    second: ControlledEvaluator,
) -> tuple[OperatorRegistry, list[ConfiguredOperatorSpec], CleaningStateGraph]:
    registry = OperatorRegistry()
    registry.register_parameter_computer(TrackingComputer())
    configured: list[ConfiguredOperatorSpec] = []
    for operator_name, evaluator in (("test.first", first), ("test.second", second)):
        operator = OperatorSpec(
            name=operator_name,
            category="test",
            required_parameters=["tracked_value"],
            evaluation_columns=[evaluator.action_column, evaluator.reason_column],
            default_config={},
            action_column=evaluator.action_column,
            reason_column=evaluator.reason_column,
            evaluator=evaluator,
        )
        registry.register_operator(operator)
        configured.append(ConfiguredOperatorSpec.from_spec(operator, {}, source="test"))
    return registry, configured, CleaningStateGraph.compile(configured, registry)


def _mark_run_unfinished(
    run_dir: Path,
    run_id: str,
    parameter_node_id: str = "parameter.tracking_computer",
    reuse_parameter: bool = True,
) -> None:
    with sqlite3.connect(run_dir / "run_state.sqlite") as connection:
        connection.execute("UPDATE cleaning_run SET status = ? WHERE run_id = ?", ("running", run_id))
        if reuse_parameter:
            connection.execute(
                "UPDATE graph_node SET status = ?, finished_at = NULL WHERE run_id = ? AND node_id != ?",
                ("pending", run_id, parameter_node_id),
            )
        else:
            connection.execute(
                "UPDATE graph_node SET status = ?, finished_at = NULL WHERE run_id = ?",
                ("pending", run_id),
            )
        connection.commit()

    state_path = run_dir / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["status"] = "running"
    payload["finished_at"] = ""
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_sqlite_status(run_dir: Path, run_id: str) -> str:
    with sqlite3.connect(run_dir / "run_state.sqlite") as connection:
        row = connection.execute("SELECT status FROM cleaning_run WHERE run_id = ?", (run_id,)).fetchone()
    assert row is not None
    return str(row[0])


def test_new_planned_run_persists_running_snapshot_before_evaluation(tmp_path: Path) -> None:
    TrackingComputer.call_count = 0
    evaluator = ControlledEvaluator()
    registry, configured, graph = _build_runtime_inputs(evaluator)
    dataset = _write_dataset(tmp_path)
    run_id = "new-run"
    run_dir = tmp_path / run_id
    running_snapshots = []

    def capture_running_snapshot(event: object) -> None:
        if getattr(event, "event_type", None) == "node_started" and getattr(event, "node_id", None) == (
            "evaluation.test.tracked"
        ):
            running_snapshots.append(JsonRunStateStore().load(run_dir / "state.json"))

    runtime = CleaningRuntime(tmp_path, registry=registry, progress_callback=capture_running_snapshot)
    result = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)

    assert result.status == "completed"
    assert TrackingComputer.call_count == 1
    assert len(running_snapshots) == 1
    assert running_snapshots[0].status == "running"
    assert running_snapshots[0].finished_at == ""
    assert (run_dir / "tables" / "parameter_table.parquet").exists()
    assert (run_dir / "manifests" / "parameter_manifest.json").exists()
    final_state = JsonRunStateStore().load(run_dir / "state.json")
    assert final_state.status == "completed"
    assert _load_sqlite_status(run_dir, run_id) == "completed"
    assert runtime.state_store is not None
    assert [(event.event_type, event.node_id) for event in runtime.state_store.list_events(run_id)] == [
        ("run_started", "runtime"),
        ("node_started", "parameter.stage"),
        ("node_completed", "parameter.stage"),
        ("node_started", "evaluation.test.tracked"),
        ("node_completed", "evaluation.test.tracked"),
        ("node_started", "merge.final_action"),
        ("node_completed", "merge.final_action"),
        ("run_completed", "runtime"),
    ]


def test_resume_reuses_parameter_node_and_preserves_started_at(tmp_path: Path) -> None:
    TrackingComputer.call_count = 0
    evaluator = ControlledEvaluator()
    registry, configured, graph = _build_runtime_inputs(evaluator)
    dataset = _write_dataset(tmp_path)
    run_id = "resume-run"
    runtime = CleaningRuntime(tmp_path, registry=registry)
    first_result = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)
    assert first_result.status == "completed"
    run_dir = tmp_path / run_id
    original_started_at = JsonRunStateStore().load(run_dir / "state.json").started_at
    assert runtime.state_store is not None
    runtime.state_store.close()
    _mark_run_unfinished(run_dir, run_id)
    calls_before_resume = TrackingComputer.call_count

    resumed = runtime.resume_graph(graph, dataset, run_id=run_id, configured_operators=configured)

    assert resumed.status == "completed"
    assert TrackingComputer.call_count == calls_before_resume
    assert evaluator.call_count == 2
    resumed_state = JsonRunStateStore().load(run_dir / "state.json")
    assert resumed_state.started_at == original_started_at
    assert resumed_state.status == "completed"


def test_new_and_resumed_failures_persist_the_same_lifecycle_boundary(tmp_path: Path) -> None:
    TrackingComputer.call_count = 0
    evaluator = ControlledEvaluator()
    evaluator.fail = True
    registry, configured, graph = _build_runtime_inputs(evaluator)
    dataset = _write_dataset(tmp_path)
    run_id = "failed-run"
    runtime = CleaningRuntime(tmp_path, registry=registry)

    failed = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)

    run_dir = tmp_path / run_id
    assert failed.status == "failed"
    first_failed_state = JsonRunStateStore().load(run_dir / "state.json")
    assert first_failed_state.status == "failed"
    assert first_failed_state.finished_at
    assert (run_dir / "tables" / "parameter_table.parquet").exists()
    assert (run_dir / "tables" / "evaluation_table.parquet").exists()
    assert _load_sqlite_status(run_dir, run_id) == "failed"
    assert runtime.state_store is not None
    assert runtime.state_store.list_events(run_id)[-1].event_type == "run_failed"
    calls_before_resume = TrackingComputer.call_count

    resumed = runtime.resume_graph(graph, dataset, run_id=run_id, configured_operators=configured)

    assert resumed.status == "failed"
    assert TrackingComputer.call_count == calls_before_resume
    resumed_failed_state = JsonRunStateStore().load(run_dir / "state.json")
    assert resumed_failed_state.status == "failed"
    assert resumed_failed_state.started_at == first_failed_state.started_at
    assert resumed_failed_state.finished_at
    assert _load_sqlite_status(run_dir, run_id) == "failed"
    assert runtime.state_store is not None
    assert runtime.state_store.list_events(run_id)[-1].event_type == "run_failed"


@pytest.mark.parametrize("resume", [False, True], ids=["new-run", "resume-run"])
def test_parameter_stage_failure_persists_failed_boundary(tmp_path: Path, resume: bool) -> None:
    computer = ControlledParameterComputer()
    evaluator = ControlledEvaluator()
    registry, configured, graph = _build_runtime_inputs(evaluator, parameter_computer=computer)
    dataset = _write_dataset(tmp_path)
    run_id = "parameter-failed-run"
    run_dir = tmp_path / run_id
    runtime = CleaningRuntime(tmp_path, registry=registry)
    original_started_at = ""

    if resume:
        completed = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)
        assert completed.status == "completed"
        original_started_at = JsonRunStateStore().load(run_dir / "state.json").started_at
        assert runtime.state_store is not None
        runtime.state_store.close()
        _mark_run_unfinished(
            run_dir,
            run_id,
            "parameter.controlled_parameter_computer",
            reuse_parameter=False,
        )
        computer.fail = True
        failed = runtime.resume_graph(graph, dataset, run_id=run_id, configured_operators=configured)
    else:
        computer.fail = True
        failed = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)

    assert failed.status == "failed"
    failed_state = JsonRunStateStore().load(run_dir / "state.json")
    assert failed_state.status == "failed"
    assert failed_state.finished_at
    if resume:
        assert failed_state.started_at == original_started_at
        assert "tracked_value" in pd.read_parquet(run_dir / "tables" / "parameter_table.parquet").columns
    assert _load_sqlite_status(run_dir, run_id) == "failed"
    assert runtime.state_store is not None
    assert runtime.state_store.list_events(run_id)[-1].event_type == "run_failed"


@pytest.mark.parametrize("resume", [False, True], ids=["new-run", "resume-run"])
def test_partial_evaluation_failure_persists_latest_tables_and_operator_states(
    tmp_path: Path,
    resume: bool,
) -> None:
    TrackingComputer.call_count = 0
    first = ControlledEvaluator("first")
    second = ControlledEvaluator("second")
    registry, configured, graph = _build_two_evaluator_inputs(first, second)
    dataset = _write_dataset(tmp_path)
    run_id = "partial-evaluation-failed-run"
    run_dir = tmp_path / run_id
    runtime = CleaningRuntime(tmp_path, registry=registry)

    if resume:
        completed = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)
        assert completed.status == "completed"
        assert runtime.state_store is not None
        runtime.state_store.close()
        _mark_run_unfinished(run_dir, run_id)
    second.fail = True

    if resume:
        failed = runtime.resume_graph(graph, dataset, run_id=run_id, configured_operators=configured)
    else:
        failed = runtime.run_graph(graph, dataset, RunOptions(run_id=run_id), configured)

    assert failed.status == "failed"
    failed_tables = read_tables(build_run_paths(run_dir))
    assert "first_action" in failed_tables.evaluation_table.columns
    assert failed_tables.evaluation_table["first_action"].tolist() == ["keep"]
    assert "second_action" not in failed_tables.evaluation_table.columns
    assert failed_tables.operator_outputs == {"test.first": ["first_action", "first_reason"]}
    failed_state = JsonRunStateStore().load(run_dir / "state.json")
    assert failed_state.status == "failed"
    assert [state.operator_name for state in failed_state.operator_states] == ["test.first"]
