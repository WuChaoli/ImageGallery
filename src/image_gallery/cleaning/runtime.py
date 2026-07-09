"""Task 5/7 的运行时组件：事件上报、重试语义和最小真实执行。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from image_gallery.cleaning.artifacts import ArtifactManager
from image_gallery.cleaning.config import ParsedOperatorConfig
from image_gallery.cleaning.context import CleanerRunContext, CleanerRunPaths
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.events import ProgressReporter, RuntimeEvent
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.preview import apply_final_action
from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore
from image_gallery.cleaning.scheduler import ParameterScheduler
from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore, OperatorRunState
from image_gallery.cleaning.tables import (
    CleaningTables,
    initialize_evaluation_table,
    initialize_parameter_table,
    write_tables,
)
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec


@dataclass(frozen=True)
class RunOptions:
    """运行参数。"""

    run_id: str
    retry_max_attempts: int = 1


@dataclass(frozen=True)
class RuntimeRunResult:
    """运行结果摘要。"""

    run_id: str
    cache_root: Path
    status: str
    attempt_count: int


class CleaningRuntime:
    """清洗运行时最小骨架。"""

    def __init__(self, cache_root: str | Path, registry: OperatorRegistry | None = None) -> None:
        self._cache_root = Path(cache_root)
        self._registry = registry if registry is not None else create_default_registry()
        self.state_store: SQLiteRunStateStore | None = None
        self._progress = ProgressReporter()
        self._artifact_manager: ArtifactManager | None = None

    def run_graph(
        self,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_options: RunOptions,
        configured_operators: list[ConfiguredOperatorSpec] | None = None,
    ) -> RuntimeRunResult:
        """执行真实运行图；缺省时回退 fake stage。"""
        if not graph.nodes:
            return self.run_fake_stage_for_test(dataset=dataset, options=run_options, fail_first_attempt=False)
        if not configured_operators:
            return self.run_fake_stage_for_test(dataset=dataset, options=run_options, fail_first_attempt=False)

        return self._run_planned_graph(graph=graph, dataset=dataset, run_options=run_options, configured_operators=configured_operators)

    def resume_graph(
        self,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_id: str | None = None,
    ) -> RuntimeRunResult:
        """占位：按 run_id 重放清洗执行。"""
        del graph
        resume_run_id = run_id or uuid4().hex
        return self.run_fake_stage_for_test(dataset=dataset, options=RunOptions(run_id=resume_run_id))

    def rerun_evaluation(
        self,
        graph: CleaningStateGraph,
        result: object,
        operators: object | None = None,
        overwrite: bool = False,
    ) -> RuntimeRunResult:
        """占位：按结果重跑算子阶段。"""
        del graph
        del operators
        del overwrite

        if not hasattr(result, "run_id"):
            run_id = uuid4().hex
            return RuntimeRunResult(run_id=run_id, cache_root=self._cache_root, status="completed", attempt_count=1)

        typed_result = cast(Any, result)
        run_id = str(typed_result.run_id)
        cache_root = typed_result.cache_root if hasattr(typed_result, "cache_root") else self._cache_root
        if isinstance(cache_root, str):
            cache_root = Path(cache_root)
        return RuntimeRunResult(run_id=run_id, cache_root=cache_root, status="completed", attempt_count=1)

    def _run_planned_graph(
        self,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_options: RunOptions,
        configured_operators: list[ConfiguredOperatorSpec],
    ) -> RuntimeRunResult:
        """按参数/算子计划执行最小真实路径。"""
        if run_options.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be positive")

        run_id = run_options.run_id
        run_dir = self._cache_root / run_id
        start_at = datetime.now(timezone.utc).isoformat()

        self._artifact_manager = ArtifactManager(run_dir / "artifacts")
        parsed_operators = [
            ParsedOperatorConfig(
                operator_name=operator_spec.operator_name,
                config=operator_spec.config,
                config_hash=operator_spec.operator_config_hash,
            )
            for operator_spec in configured_operators
        ]
        planner = CleaningRunPlanner(self._registry)
        plan = planner.compile(parsed_operators)

        parameter_table = initialize_parameter_table(dataset)
        evaluation_table = initialize_evaluation_table(parameter_table)
        tables = CleaningTables(
            parameter_table=parameter_table,
            evaluation_table=evaluation_table,
            operator_outputs={},
            parameter_manifest={},
        )

        paths = CleanerRunPaths(
            run_dir=run_dir,
            parameter_table_path=run_dir / "parameter_table.parquet",
            evaluation_table_path=run_dir / "evaluation_table.parquet",
            operator_outputs_path=run_dir / "operator_outputs.yaml",
            parameter_manifest_path=run_dir / "parameter_manifest.json",
            relations_dir=run_dir / "relations",
            artifacts_dir=run_dir / "artifacts",
            state_path=run_dir / "state.json",
        )
        context = CleanerRunContext(
            run_id=run_id,
            dataset=dataset,
            dataset_fingerprint=dataset.fingerprint(),
            cleaner_type="basic",
            operator_configs=parsed_operators,
            paths=paths,
        )

        self.state_store = SQLiteRunStateStore.initialize(
            run_dir=run_dir,
            run_record=RunRecord(
                run_id=run_id,
                cleaner_type="basic",
                status="running",
                dataset_fingerprint=dataset.fingerprint(),
                plan_hash=graph.plan_hash,
                label="basic-run",
                tags=[],
                sample_size=None,
                sample_rule=None,
            ),
        )
        self.state_store.record_graph(graph)

        self._report(
            RunEventContext(run_id),
            "run_started",
            "runtime",
            message="runtime started",
        )

        attempt_count = 1
        try:
            scheduler = ParameterScheduler(self._registry)
            schedule_result = scheduler.run(plan.parameter_plan, context, tables)
            tables = schedule_result.tables
            evaluator = OperatorEvaluator()
            operator_states: list[OperatorRunState] = []
            for resolved in plan.resolved_operator_runs:
                tables, operator_state = evaluator.evaluate(resolved, tables)
                operator_states.append(operator_state)

            tables = CleaningTables(
                parameter_table=tables.parameter_table,
                evaluation_table=apply_final_action(tables.evaluation_table, tables.operator_outputs),
                operator_outputs=tables.operator_outputs,
                parameter_manifest=tables.parameter_manifest,
            )
            write_tables(tables=tables, paths=paths)

            JsonRunStateStore().save(
                CleanerRunState(
                    run_id=run_id,
                    dataset_fingerprint=dataset.fingerprint(),
                    cleaner_type="basic",
                    enabled_operator_configs=[{item.operator_name: dict(item.config)} for item in parsed_operators],
                    operator_config_hashes={item.operator_name: item.config_hash for item in parsed_operators},
                    parameter_config_hashes={},
                    parameter_table_path=str(paths.parameter_table_path),
                    evaluation_table_path=str(paths.evaluation_table_path),
                    operator_outputs_path=str(paths.operator_outputs_path),
                    parameter_manifest_path=str(paths.parameter_manifest_path),
                    relation_paths=schedule_result.relation_paths,
                    artifact_paths=schedule_result.artifact_paths,
                    started_at=start_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    status="completed",
                    operator_states=operator_states,
                ),
                paths.state_path,
            )
            self._report(
                RunEventContext(run_id),
                "run_completed",
                "runtime",
                message="run completed",
            )
            self._set_run_status(run_id=run_id, status="completed")
            return RuntimeRunResult(
                run_id=run_id,
                cache_root=self._cache_root,
                status="completed",
                attempt_count=attempt_count,
            )
        except Exception:
            self._report(
                RunEventContext(run_id),
                "run_failed",
                "runtime",
                message="run failed",
            )
            self._set_run_status(run_id=run_id, status="failed")
            return RuntimeRunResult(
                run_id=run_id,
                cache_root=self._cache_root,
                status="failed",
                attempt_count=attempt_count,
            )

    def run_fake_stage_for_test(
        self,
        dataset: Dataset,
        options: RunOptions,
        fail_first_attempt: bool = False,
    ) -> RuntimeRunResult:
        """仅用于测试的阶段执行入口：用于验证重试、状态存储和事件链路。"""
        if options.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be positive")

        run_id = options.run_id
        run_dir = self._cache_root / run_id
        self._artifact_manager = ArtifactManager(run_dir / "artifacts")
        self.state_store = SQLiteRunStateStore.initialize(
            run_dir=run_dir,
            run_record=RunRecord(
                run_id=run_id,
                cleaner_type="test-runtime",
                status="running",
                dataset_fingerprint=dataset.fingerprint(),
                plan_hash="test-fake-plan",
                label="test-fake",
                tags=[],
                sample_size=None,
                sample_rule=None,
            ),
        )

        self._report(RunEventContext(run_id), "run_started", "runtime", message="runtime started")

        attempt_count = 0
        for attempt in range(1, options.retry_max_attempts + 1):
            attempt_count = attempt
            self._report(
                RunEventContext(run_id),
                "parameter_stage_started",
                "parameter.fake",
                message="stage attempt started",
                payload={"attempt": attempt},
            )
            if attempt == 1 and fail_first_attempt:
                self._report(
                    RunEventContext(run_id),
                    "parameter_stage_failed",
                    "parameter.fake",
                    message="simulated failure",
                    payload={"attempt": attempt},
                )
                if attempt >= options.retry_max_attempts:
                    break
                continue

            _ = dataset.count()
            self._report(
                RunEventContext(run_id),
                "parameter_stage_completed",
                "parameter.fake",
                message="stage completed",
                payload={"attempt": attempt},
            )
            self._report(
                RunEventContext(run_id),
                "run_completed",
                "runtime",
                message="run completed",
                payload={"attempt_count": attempt},
            )
            self._set_run_status(run_id=run_id, status="completed")
            return RuntimeRunResult(
                run_id=run_id,
                cache_root=self._cache_root,
                status="completed",
                attempt_count=attempt_count,
            )

        self._report(
            RunEventContext(run_id),
            "run_failed",
            "runtime",
            message="run failed",
            payload={"attempt_count": attempt_count},
        )
        self._set_run_status(run_id=run_id, status="failed")
        return RuntimeRunResult(
            run_id=run_id,
            cache_root=self._cache_root,
            status="failed",
            attempt_count=attempt_count,
        )

    def _set_run_status(self, run_id: str, status: str) -> None:
        """同步运行主状态到 SQLite。"""
        if self.state_store is None:
            raise RuntimeError("state store not initialized")
        self.state_store.update_run_status(run_id=run_id, status=status)

    def _report(
        self,
        context: RunEventContext,
        event_type: str,
        node_id: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> RuntimeEvent:
        """统一记录并持久化一次 runtime 事件。"""
        event = self._progress.emit(
            event_type=event_type,
            run_id=context.run_id,
            node_id=node_id,
            message=message,
            payload=payload,
        )
        if self.state_store is None:
            raise RuntimeError("state store not initialized")
        self.state_store.record_event(event)
        return event


@dataclass(frozen=True)
class RunEventContext:
    """传递 run_id 的轻量上下文。"""

    run_id: str
