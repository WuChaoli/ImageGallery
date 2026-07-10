"""Task 5/7 的运行时组件：事件上报、重试语义和最小真实执行。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.artifacts import ArtifactManager
from image_gallery.cleaning.config import ParsedOperatorConfig
from image_gallery.cleaning.context import CleanerRunContext, CleanerRunPaths, build_run_paths
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.events import ProgressReporter, RuntimeEvent
from image_gallery.cleaning.graph import CleaningStateGraph, GraphNode
from image_gallery.cleaning.planner import CleaningRunPlanner, CompiledCleaningPlan
from image_gallery.cleaning.preview import apply_final_action
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore
from image_gallery.cleaning.scheduler import ParameterScheduler
from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore, OperatorRunState
from image_gallery.cleaning.tables import (
    CleaningTables,
    initialize_evaluation_table,
    initialize_parameter_table,
    read_tables,
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
    sample_rule: dict[str, object] | None = None
    label: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeRunResult:
    """运行结果摘要。"""

    run_id: str
    cache_root: Path
    status: str
    attempt_count: int


class CleaningRuntime:
    """清洗运行时最小骨架。"""

    def __init__(
        self,
        cache_root: str | Path,
        registry: OperatorRegistry | None = None,
        progress_callback: Callable[[RuntimeEvent], None] | None = None,
    ) -> None:
        """初始化运行时组件。"""
        self._cache_root = Path(cache_root)
        self._registry = registry if registry is not None else create_default_registry()
        self.state_store: SQLiteRunStateStore | None = None
        self._progress = ProgressReporter(progress_callback)
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

        return self._run_planned_graph(
            graph=graph,
            dataset=dataset,
            run_options=run_options,
            configured_operators=configured_operators,
        )

    def resume_graph(
        self,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_id: str | None = None,
        result: CleanerResult | None = None,
        configured_operators: list[ConfiguredOperatorSpec] | None = None,
        sample_rule: dict[str, object] | None = None,
    ) -> RuntimeRunResult:
        """恢复历史运行；已完成运行直接复用，未完成运行回退到整次重跑。"""
        resume_run_id, cache_root = self._resolve_run_reference(run_id=run_id, result=result)
        run_dir = cache_root / resume_run_id
        store = SQLiteRunStateStore.open_existing(run_dir, resume_run_id)
        try:
            run_record = store.load_run(resume_run_id)
            self._validate_run_record(
                run_record=run_record,
                dataset=dataset,
                graph=graph,
                sample_rule=sample_rule,
            )
            graph_nodes = self._validate_graph_nodes(store=store, run_id=resume_run_id, expected_graph=graph)
            self._validate_run_outputs(
                run_dir=run_dir,
                run_record=run_record,
                trusted_parameter_hashes=_parameter_config_hashes_from_graph_nodes(graph_nodes),
                trusted_parameter_owners=_parameter_owner_computers_from_graph_nodes(graph_nodes),
            )
            if run_record.status == "completed":
                return RuntimeRunResult(
                    run_id=resume_run_id,
                    cache_root=cache_root,
                    status="completed",
                    attempt_count=1,
                )
        finally:
            store.close()

        if configured_operators is None:
            raise ValueError("configured_operators is required when resuming an unfinished run")
        return self._resume_planned_graph(
            graph=graph,
            dataset=dataset,
            run_options=RunOptions(run_id=resume_run_id, sample_rule=run_record.sample_rule),
            configured_operators=configured_operators,
            run_dir=run_dir,
        )

    def rerun_evaluation(
        self,
        current_graph: CleaningStateGraph,
        rerun_graph: CleaningStateGraph,
        result: CleanerResult,
        configured_operators: list[ConfiguredOperatorSpec],
        operators: object | None = None,
        overwrite: bool = False,
    ) -> RuntimeRunResult:
        """复用现有参数表与 artifacts，仅重跑 evaluation/merge。"""
        del operators
        del overwrite
        run_id, cache_root = self._resolve_run_reference(result=result)
        run_dir = cache_root / run_id
        store = SQLiteRunStateStore.open_existing(run_dir, run_id)
        try:
            run_record = store.load_run(run_id)
            self._validate_run_record(
                run_record=run_record,
                dataset=Dataset.load(str(run_dir / "parameter_table.parquet")),
                graph=current_graph,
                sample_rule=run_record.sample_rule,
                skip_dataset_validation=True,
            )
            graph_nodes = self._validate_graph_nodes(store=store, run_id=run_id, expected_graph=current_graph)
            self._validate_run_outputs(
                run_dir=run_dir,
                run_record=run_record,
                trusted_parameter_hashes=_parameter_config_hashes_from_graph_nodes(graph_nodes),
                trusted_parameter_owners=_parameter_owner_computers_from_graph_nodes(graph_nodes),
            )
            self._validate_rerun_graph_change(current_graph=current_graph, rerun_graph=rerun_graph)

            planner = CleaningRunPlanner(self._registry)
            rerun_plan = planner.compile(
                [
                    ParsedOperatorConfig(
                        operator_name=operator_spec.operator_name,
                        config=operator_spec.config,
                        config_hash=operator_spec.operator_config_hash,
                    )
                    for operator_spec in configured_operators
                ]
            )

            state_path = build_run_paths(run_dir).state_path
            state = JsonRunStateStore().load(state_path)
            current_parameter_hashes = {
                node.computer_name: node.config_hash
                for node in current_graph.nodes
                if node.node_type == "parameter" and node.computer_name is not None
            }
            next_parameter_hashes = {step.computer_name: step.config_hash for step in rerun_plan.parameter_plan.steps}
            if current_parameter_hashes != next_parameter_hashes:
                raise ValueError("parameter computer config changed; evaluation-only rerun is not allowed")

            paths = build_run_paths(run_dir)
            persisted_tables = read_tables(paths)
            rerun_tables = CleaningTables(
                parameter_table=persisted_tables.parameter_table,
                evaluation_table=initialize_evaluation_table(persisted_tables.parameter_table),
                operator_outputs={},
                parameter_manifest=persisted_tables.parameter_manifest,
            )
            evaluator = OperatorEvaluator()
            operator_states: list[OperatorRunState] = []
            for resolved in rerun_plan.resolved_operator_runs:
                rerun_tables, operator_state = evaluator.evaluate(resolved, rerun_tables)
                operator_states.append(operator_state)
            rerun_tables = CleaningTables(
                parameter_table=rerun_tables.parameter_table,
                evaluation_table=apply_final_action(rerun_tables.evaluation_table, rerun_tables.operator_outputs),
                operator_outputs=rerun_tables.operator_outputs,
                parameter_manifest=rerun_tables.parameter_manifest,
            )
            write_tables(tables=rerun_tables, paths=paths)

            updated_record = RunRecord(
                run_id=run_record.run_id,
                cleaner_type=run_record.cleaner_type,
                status="running",
                dataset_fingerprint=run_record.dataset_fingerprint,
                plan_hash=rerun_graph.plan_hash,
                label=run_record.label,
                tags=run_record.tags,
                sample_size=run_record.sample_size,
                sample_rule=run_record.sample_rule,
            )
            store.save_run_record(updated_record)
            store.record_graph(rerun_graph)
            JsonRunStateStore().save(
                CleanerRunState(
                    run_id=run_id,
                    dataset_fingerprint=state.dataset_fingerprint,
                    cleaner_type=state.cleaner_type,
                    enabled_operator_configs=[{item.operator_name: dict(item.config)} for item in configured_operators],
                    operator_config_hashes=rerun_plan.operator_config_hashes,
                    parameter_config_hashes=next_parameter_hashes,
                    parameter_table_path=state.parameter_table_path,
                    evaluation_table_path=state.evaluation_table_path,
                    operator_outputs_path=state.operator_outputs_path,
                    parameter_manifest_path=state.parameter_manifest_path,
                    relation_paths=state.relation_paths,
                    artifact_paths=state.artifact_paths,
                    started_at=state.started_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    status="completed",
                    operator_states=operator_states,
                ),
                state_path,
            )
            store.update_run_status(run_id=run_id, status="completed")
        finally:
            store.close()
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

        paths = build_run_paths(run_dir)
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
                label=run_options.label or "basic-run",
                tags=run_options.tags,
                sample_size=_sample_size(run_options.sample_rule),
                sample_rule=run_options.sample_rule,
            ),
        )
        self.state_store.record_graph(graph)
        self._write_runtime_manifests(run_dir=run_dir, graph=graph)

        self._report(
            RunEventContext(run_id),
            "run_started",
            "runtime",
            message="runtime started",
        )

        attempt_count = 1
        artifact_paths: dict[str, str] = {}
        relation_paths: dict[str, str] = {}
        operator_states: list[OperatorRunState] = []
        try:
            scheduler = ParameterScheduler(self._registry)
            self._report(
                RunEventContext(run_id),
                "node_started",
                "parameter.stage",
                message="parameter stage started",
            )
            schedule_result = scheduler.run(plan.parameter_plan, context, tables, state_store=self.state_store)
            tables = schedule_result.tables
            self._report(
                RunEventContext(run_id),
                "node_completed",
                "parameter.stage",
                message="parameter stage completed",
            )
            write_tables(tables=tables, paths=paths)
            artifact_paths = dict(schedule_result.artifact_paths)
            relation_paths = dict(schedule_result.relation_paths)
            self._save_run_state(
                run_id=run_id,
                dataset_fingerprint=dataset.fingerprint(),
                parsed_operators=parsed_operators,
                operator_config_hashes=plan.operator_config_hashes,
                parameter_config_hashes={
                    step.computer_name: step.config_hash for step in plan.parameter_plan.steps
                },
                paths=paths,
                artifact_paths=artifact_paths,
                relation_paths=relation_paths,
                started_at=start_at,
                finished_at="",
                status="running",
                operator_states=[],
            )
            return self._complete_planned_run(
                run_id=run_id,
                dataset_fingerprint=dataset.fingerprint(),
                parsed_operators=parsed_operators,
                plan=plan,
                paths=paths,
                tables=tables,
                artifact_paths=artifact_paths,
                relation_paths=relation_paths,
                started_at=start_at,
            )
        except Exception:
            if paths.run_dir.exists():
                write_tables(tables=tables, paths=paths)
                self._save_run_state(
                    run_id=run_id,
                    dataset_fingerprint=dataset.fingerprint(),
                    parsed_operators=parsed_operators,
                    operator_config_hashes=plan.operator_config_hashes,
                    parameter_config_hashes={
                        step.computer_name: step.config_hash for step in plan.parameter_plan.steps
                    },
                    paths=paths,
                    artifact_paths=artifact_paths,
                    relation_paths=relation_paths,
                    started_at=start_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    status="failed",
                    operator_states=operator_states,
                )
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

    def _resume_planned_graph(
        self,
        *,
        graph: CleaningStateGraph,
        dataset: Dataset,
        run_options: RunOptions,
        configured_operators: list[ConfiguredOperatorSpec],
        run_dir: Path,
    ) -> RuntimeRunResult:
        """基于已有 run_dir 复用已完成参数节点并继续执行。"""
        run_id = run_options.run_id
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
        plan = CleaningRunPlanner(self._registry).compile(parsed_operators)
        paths = build_run_paths(run_dir)
        persisted_state = JsonRunStateStore().load(paths.state_path)
        persisted_tables = read_tables(paths)
        tables = CleaningTables(
            parameter_table=persisted_tables.parameter_table,
            evaluation_table=initialize_evaluation_table(persisted_tables.parameter_table),
            operator_outputs={},
            parameter_manifest=persisted_tables.parameter_manifest,
        )
        context = CleanerRunContext(
            run_id=run_id,
            dataset=dataset,
            dataset_fingerprint=dataset.fingerprint(),
            cleaner_type="basic",
            operator_configs=parsed_operators,
            paths=paths,
        )

        self.state_store = SQLiteRunStateStore.open_existing(run_dir, run_id)
        self._set_run_status(run_id=run_id, status="running")
        self._report(
            RunEventContext(run_id),
            "run_started",
            "runtime",
            message="runtime resumed",
        )

        artifact_paths = dict(persisted_state.artifact_paths)
        relation_paths = dict(persisted_state.relation_paths)
        operator_states: list[OperatorRunState] = []
        try:
            completed_node_ids = {
                node_id
                for node_id, status in self.state_store.list_graph_node_statuses(run_id).items()
                if status == "completed"
            }
            self._report(
                RunEventContext(run_id),
                "node_started",
                "parameter.stage",
                message="parameter stage started",
            )
            schedule_result = ParameterScheduler(self._registry).run(
                plan.parameter_plan,
                context,
                tables,
                state_store=self.state_store,
                completed_node_ids=completed_node_ids,
            )
            tables = schedule_result.tables
            self._report(
                RunEventContext(run_id),
                "node_completed",
                "parameter.stage",
                message="parameter stage completed",
            )
            artifact_paths.update(schedule_result.artifact_paths)
            relation_paths.update(schedule_result.relation_paths)
            write_tables(tables=tables, paths=paths)
            self._save_run_state(
                run_id=run_id,
                dataset_fingerprint=dataset.fingerprint(),
                parsed_operators=parsed_operators,
                operator_config_hashes=plan.operator_config_hashes,
                parameter_config_hashes={
                    step.computer_name: step.config_hash for step in plan.parameter_plan.steps
                },
                paths=paths,
                artifact_paths=artifact_paths,
                relation_paths=relation_paths,
                started_at=persisted_state.started_at or start_at,
                finished_at="",
                status="running",
                operator_states=[],
            )
            return self._complete_planned_run(
                run_id=run_id,
                dataset_fingerprint=dataset.fingerprint(),
                parsed_operators=parsed_operators,
                plan=plan,
                paths=paths,
                tables=tables,
                artifact_paths=artifact_paths,
                relation_paths=relation_paths,
                started_at=persisted_state.started_at or start_at,
            )
        except Exception:
            write_tables(tables=tables, paths=paths)
            self._save_run_state(
                run_id=run_id,
                dataset_fingerprint=dataset.fingerprint(),
                parsed_operators=parsed_operators,
                operator_config_hashes=plan.operator_config_hashes,
                parameter_config_hashes={
                    step.computer_name: step.config_hash for step in plan.parameter_plan.steps
                },
                paths=paths,
                artifact_paths=artifact_paths,
                relation_paths=relation_paths,
                started_at=persisted_state.started_at or start_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                status="failed",
                operator_states=operator_states,
            )
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
                attempt_count=1,
            )

    def _complete_planned_run(
        self,
        *,
        run_id: str,
        dataset_fingerprint: str,
        parsed_operators: list[ParsedOperatorConfig],
        plan: CompiledCleaningPlan,
        paths: CleanerRunPaths,
        tables: CleaningTables,
        artifact_paths: dict[str, str],
        relation_paths: dict[str, str],
        started_at: str,
    ) -> RuntimeRunResult:
        """执行 evaluation/merge，并把最终状态写回运行目录。"""
        if self.state_store is None:
            raise RuntimeError("state store not initialized")

        evaluator = OperatorEvaluator()
        operator_states: list[OperatorRunState] = []
        for resolved in plan.resolved_operator_runs:
            node_id = f"evaluation.{resolved.spec.name}"
            self._report(
                RunEventContext(run_id),
                "node_started",
                node_id,
                message=f"{node_id} started",
            )
            self.state_store.record_node_started(node_id)
            try:
                tables, operator_state = evaluator.evaluate(resolved, tables)
            except Exception:
                self.state_store.record_node_failed(node_id)
                self._report(
                    RunEventContext(run_id),
                    "node_failed",
                    node_id,
                    message=f"{node_id} failed",
                )
                raise
            self.state_store.record_node_completed(node_id)
            self._report(
                RunEventContext(run_id),
                "node_completed",
                node_id,
                message=f"{node_id} completed",
            )
            operator_states.append(operator_state)

        merge_node_id = "merge.final_action"
        self._report(
            RunEventContext(run_id),
            "node_started",
            merge_node_id,
            message="merge.final_action started",
        )
        self.state_store.record_node_started(merge_node_id)
        try:
            tables = CleaningTables(
                parameter_table=tables.parameter_table,
                evaluation_table=apply_final_action(tables.evaluation_table, tables.operator_outputs),
                operator_outputs=tables.operator_outputs,
                parameter_manifest=tables.parameter_manifest,
            )
        except Exception:
            self.state_store.record_node_failed(merge_node_id)
            self._report(
                RunEventContext(run_id),
                "node_failed",
                merge_node_id,
                message="merge.final_action failed",
            )
            raise
        self.state_store.record_node_completed(merge_node_id)
        self._report(
            RunEventContext(run_id),
            "node_completed",
            merge_node_id,
            message="merge.final_action completed",
        )
        write_tables(tables=tables, paths=paths)
        self._save_run_state(
            run_id=run_id,
            dataset_fingerprint=dataset_fingerprint,
            parsed_operators=parsed_operators,
            operator_config_hashes=plan.operator_config_hashes,
            parameter_config_hashes={
                step.computer_name: step.config_hash for step in plan.parameter_plan.steps
            },
            paths=paths,
            artifact_paths=artifact_paths,
            relation_paths=relation_paths,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            status="completed",
            operator_states=operator_states,
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
            attempt_count=1,
        )

    def _write_runtime_manifests(self, *, run_dir: Path, graph: CleaningStateGraph) -> None:
        """写出供 Result 只读导出的运行计划和 artifact 清单。"""
        manifests_dir = run_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        (manifests_dir / "execution_plan.json").write_text(
            json.dumps(
                {
                    "plan_hash": graph.plan_hash,
                    "nodes": graph.to_frame().to_dict(orient="records"),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        _write_artifacts_manifest(run_dir=run_dir, artifact_paths={}, relation_paths={})

    def _save_run_state(
        self,
        *,
        run_id: str,
        dataset_fingerprint: str,
        parsed_operators: list[ParsedOperatorConfig],
        operator_config_hashes: dict[str, str],
        parameter_config_hashes: dict[str, str],
        paths: CleanerRunPaths,
        artifact_paths: dict[str, str],
        relation_paths: dict[str, str],
        started_at: str,
        finished_at: str,
        status: str,
        operator_states: list[OperatorRunState],
    ) -> None:
        """把当前运行快照持久化到 state.json。"""
        JsonRunStateStore().save(
            CleanerRunState(
                run_id=run_id,
                dataset_fingerprint=dataset_fingerprint,
                cleaner_type="basic",
                enabled_operator_configs=[{item.operator_name: dict(item.config)} for item in parsed_operators],
                operator_config_hashes=operator_config_hashes,
                parameter_config_hashes=parameter_config_hashes,
                parameter_table_path=str(paths.parameter_table_path),
                evaluation_table_path=str(paths.evaluation_table_path),
                operator_outputs_path=str(paths.operator_outputs_path),
                parameter_manifest_path=str(paths.parameter_manifest_path),
                relation_paths=relation_paths,
                artifact_paths=artifact_paths,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                operator_states=operator_states,
            ),
            paths.state_path,
        )
        _write_artifacts_manifest(
            run_dir=paths.run_dir,
            artifact_paths=artifact_paths,
            relation_paths=relation_paths,
        )

    def _resolve_run_reference(
        self,
        *,
        run_id: str | None = None,
        result: CleanerResult | None = None,
    ) -> tuple[str, Path]:
        """从 run_id / CleanerResult 中解析运行目录。"""
        resolved_run_id = run_id
        cache_root = self._cache_root
        if result is not None:
            if resolved_run_id is not None and resolved_run_id != result.run_id:
                raise ValueError("run_id and result.run_id must match")
            resolved_run_id = result.run_id
            cache_root = result._cache_root
        if resolved_run_id is None:
            raise ValueError("run_id or result is required")
        return resolved_run_id, Path(cache_root)

    def _validate_run_record(
        self,
        *,
        run_record: RunRecord,
        dataset: Dataset,
        graph: CleaningStateGraph,
        sample_rule: dict[str, object] | None,
        skip_dataset_validation: bool = False,
    ) -> None:
        """校验 resume/rerun 是否仍指向同一份输入与图计划。"""
        expected_sample_rule = run_record.sample_rule if sample_rule is None else sample_rule
        if expected_sample_rule != run_record.sample_rule:
            raise ValueError("sample rule does not match the recorded run")
        if not skip_dataset_validation and run_record.dataset_fingerprint != dataset.fingerprint():
            raise ValueError("dataset fingerprint does not match the recorded run")
        if run_record.plan_hash != graph.plan_hash:
            raise ValueError("plan hash does not match the recorded run")

    def _validate_graph_nodes(
        self,
        *,
        store: SQLiteRunStateStore,
        run_id: str,
        expected_graph: CleaningStateGraph,
    ) -> tuple[GraphNode, ...]:
        """校验持久化 graph node 与当前编译图完全一致。"""
        persisted = {node.node_id: node for node in store.list_graph_nodes(run_id)}
        expected = {node.node_id: node for node in expected_graph.nodes}
        if persisted.keys() != expected.keys():
            raise ValueError("graph nodes do not match the recorded run")
        for node_id, expected_node in expected.items():
            persisted_node = persisted[node_id]
            if persisted_node != expected_node:
                raise ValueError(f"graph node mismatch: {node_id}")
        return tuple(persisted[node.node_id] for node in expected_graph.nodes)

    def _validate_run_outputs(
        self,
        *,
        run_dir: Path,
        run_record: RunRecord,
        trusted_parameter_hashes: dict[str, str],
        trusted_parameter_owners: dict[str, str],
    ) -> None:
        """校验运行目录里的表、artifact 和 manifest 仍然完整可复用。"""
        del run_record
        paths = build_run_paths(run_dir)
        if not paths.parameter_table_path.exists():
            raise FileNotFoundError(f"parameter table missing: {paths.parameter_table_path}")
        if not paths.evaluation_table_path.exists():
            raise FileNotFoundError(f"evaluation table missing: {paths.evaluation_table_path}")
        if not paths.parameter_manifest_path.exists():
            raise FileNotFoundError(f"parameter manifest missing: {paths.parameter_manifest_path}")
        if not paths.state_path.exists():
            raise FileNotFoundError(f"state file missing: {paths.state_path}")

        parameter_manifest = json.loads(paths.parameter_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(parameter_manifest, dict):
            raise ValueError("parameter manifest payload must be a JSON object")
        parameter_table_columns = set(pd.read_parquet(paths.parameter_table_path).columns)
        missing_parameter_columns = sorted(set(trusted_parameter_owners) - parameter_table_columns)
        if missing_parameter_columns:
            raise ValueError(f"parameter table missing graph-produced columns: {missing_parameter_columns}")
        missing_manifest_entries = sorted(set(trusted_parameter_owners) - set(parameter_manifest))
        if missing_manifest_entries:
            raise ValueError(f"parameter manifest missing graph-produced entries: {missing_manifest_entries}")

        state = JsonRunStateStore().load(paths.state_path)
        if state.parameter_config_hashes != trusted_parameter_hashes:
            raise ValueError("state parameter config hashes do not match the recorded graph")
        for artifact_name, artifact_path in state.artifact_paths.items():
            owner = _artifact_owner_computer(artifact_name)
            self._validate_artifact_ref(
                artifact_name=artifact_name,
                artifact_path=Path(artifact_path),
                expected_config_hash=_expected_owner_config_hash(
                    trusted_parameter_hashes,
                    owner,
                    f"artifact manifest config hash mismatch: {artifact_name}",
                ),
            )
        for relation_name, relation_path in state.relation_paths.items():
            owner = _relation_owner_computer(relation_name)
            self._validate_relation_manifest(
                relation_name=relation_name,
                relation_path=Path(relation_path),
                expected_config_hash=_expected_owner_config_hash(
                    trusted_parameter_hashes,
                    owner,
                    f"relation manifest config hash mismatch: {relation_name}",
                ),
            )
        for parameter_name, manifest in parameter_manifest.items():
            if not isinstance(manifest, dict):
                raise ValueError(f"parameter manifest entry must be a JSON object: {parameter_name}")
            owner = trusted_parameter_owners.get(parameter_name)
            expected_config_hash = _expected_owner_config_hash(
                trusted_parameter_hashes,
                owner,
                f"parameter manifest config hash mismatch: {parameter_name}",
            )
            if expected_config_hash is not None and manifest.get("config_hash") != expected_config_hash:
                raise ValueError(f"parameter manifest config hash mismatch: {parameter_name}")
            artifact_ref = manifest.get("artifact_ref")
            if isinstance(artifact_ref, str) and artifact_ref:
                self._validate_artifact_ref(
                    artifact_name=parameter_name,
                    artifact_path=Path(artifact_ref),
                    expected_config_hash=expected_config_hash,
                )

    def _validate_artifact_ref(
        self,
        *,
        artifact_name: str,
        artifact_path: Path,
        expected_config_hash: str | None,
    ) -> None:
        """按 artifact 类型检查语义 manifest / 通用 dataframe manifest。"""
        if not artifact_path.exists():
            raise FileNotFoundError(f"artifact missing: {artifact_path}")

        manifest_path: Path | None = None
        if artifact_path.is_dir():
            manifest_path = artifact_path / "manifest.json"
        elif artifact_path.suffix == ".parquet":
            manifest_path = artifact_path.with_name(f"{artifact_path.name}.manifest.json")
        elif artifact_path.name == "faiss.index":
            manifest_path = artifact_path.parent / "manifest.json"

        if manifest_path is None:
            raise ValueError(f"tracked artifact ref requires a manifest: {artifact_name}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"artifact manifest missing: {manifest_path}")

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        config_hash = payload.get("config_hash")
        if expected_config_hash is not None and config_hash != expected_config_hash:
            raise ValueError(f"artifact manifest config hash mismatch: {artifact_name}")

    def _validate_relation_manifest(
        self,
        *,
        relation_name: str,
        relation_path: Path,
        expected_config_hash: str | None,
    ) -> None:
        """校验关系表及其 manifest。"""
        if not relation_path.exists():
            raise FileNotFoundError(f"relation table missing: {relation_path}")
        manifest_path = relation_path.with_name(f"{relation_path.name}.manifest.json")
        if not manifest_path.exists():
            raise FileNotFoundError(f"relation manifest missing: {manifest_path}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("relation_name") != relation_name:
            raise ValueError(f"relation manifest mismatch: {relation_name}")
        if expected_config_hash is not None and payload.get("config_hash") != expected_config_hash:
            raise ValueError(f"relation manifest config hash mismatch: {relation_name}")
        artifact_refs = payload.get("artifact_refs", [])
        if not isinstance(artifact_refs, list):
            raise ValueError(f"relation manifest artifact refs must be a list: {relation_name}")
        for artifact_ref in artifact_refs:
            if not isinstance(artifact_ref, str) or not artifact_ref:
                raise ValueError(f"relation manifest artifact ref must be non-empty: {relation_name}")
            self._validate_artifact_ref(
                artifact_name=f"{relation_name}.artifact_ref",
                artifact_path=Path(artifact_ref),
                expected_config_hash=expected_config_hash,
            )

    def _validate_rerun_graph_change(
        self,
        *,
        current_graph: CleaningStateGraph,
        rerun_graph: CleaningStateGraph,
    ) -> None:
        """允许 evaluation config 变化，但拒绝图结构和参数节点变化。"""
        current_nodes = {node.node_id: node for node in current_graph.nodes}
        rerun_nodes = {node.node_id: node for node in rerun_graph.nodes}
        if current_nodes.keys() != rerun_nodes.keys():
            raise ValueError("graph changed; evaluation-only rerun is not allowed")

        for node_id, current_node in current_nodes.items():
            rerun_node = rerun_nodes[node_id]
            if current_node.node_type == "parameter":
                if current_node != rerun_node:
                    if current_node.config_hash != rerun_node.config_hash:
                        raise ValueError("parameter computer config changed; evaluation-only rerun is not allowed")
                    raise ValueError("graph changed; evaluation-only rerun is not allowed")
                continue
            if current_node.node_type == "evaluation":
                comparable_current = (
                    current_node.node_id,
                    current_node.node_type,
                    current_node.operator_name,
                    current_node.computer_name,
                    current_node.stage_name,
                    current_node.execution_mode,
                    current_node.required_parameters,
                    current_node.produced_parameters,
                    current_node.policy_hash,
                    current_node.upstream_node_ids,
                    current_node.checkpoint_strategy,
                )
                comparable_rerun = (
                    rerun_node.node_id,
                    rerun_node.node_type,
                    rerun_node.operator_name,
                    rerun_node.computer_name,
                    rerun_node.stage_name,
                    rerun_node.execution_mode,
                    rerun_node.required_parameters,
                    rerun_node.produced_parameters,
                    rerun_node.policy_hash,
                    rerun_node.upstream_node_ids,
                    rerun_node.checkpoint_strategy,
                )
                if comparable_current != comparable_rerun:
                    raise ValueError("graph changed; evaluation-only rerun is not allowed")
                continue
            if current_node != rerun_node:
                raise ValueError("graph changed; evaluation-only rerun is not allowed")

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


def _sample_size(sample_rule: dict[str, object] | None) -> int | None:
    """从 sample 规则中提取最常见的样本数表示。"""
    if sample_rule is None:
        return None
    raw = sample_rule.get("n")
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise TypeError("sample.n must be an integer")
    if isinstance(raw, (int, float, str, bytes)):
        return int(raw)
    raise TypeError("sample.n must be an integer")


def _parameter_config_hashes_from_graph_nodes(graph_nodes: tuple[GraphNode, ...]) -> dict[str, str]:
    """从已验证 graph nodes 提取可信 parameter computer config_hash。"""
    return {
        node.computer_name: node.config_hash
        for node in graph_nodes
        if node.node_type == "parameter" and node.computer_name is not None
    }


def _write_artifacts_manifest(
    *,
    run_dir: Path,
    artifact_paths: dict[str, str],
    relation_paths: dict[str, str],
) -> None:
    """写出不包含绝对 cache 路径的 artifact/relation manifest。"""
    manifests_dir = run_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    def relative_uri(path: str) -> str:
        path_obj = Path(path)
        try:
            return path_obj.resolve().relative_to(run_dir.resolve()).as_posix()
        except ValueError:
            return path_obj.name

    payload = {
        "artifacts": [
            {"name": name, "uri": relative_uri(path), "status": "committed"}
            for name, path in sorted(artifact_paths.items())
        ],
        "relations": [
            {"name": name, "uri": relative_uri(path), "status": "committed"}
            for name, path in sorted(relation_paths.items())
        ],
    }
    (manifests_dir / "artifacts.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parameter_owner_computers_from_graph_nodes(graph_nodes: tuple[GraphNode, ...]) -> dict[str, str]:
    """从已验证 graph nodes 提取本次运行实际消费的 parameter -> computer 映射。"""
    consumed_parameters = {
        parameter_name
        for node in graph_nodes
        if node.node_type in {"parameter", "evaluation"}
        for parameter_name in node.required_parameters
    }
    owners: dict[str, str] = {}
    for node in graph_nodes:
        if node.node_type != "parameter" or node.computer_name is None:
            continue
        for parameter_name in node.produced_parameters & consumed_parameters:
            owners[parameter_name] = node.computer_name
    return owners


def _expected_owner_config_hash(
    trusted_parameter_hashes: dict[str, str],
    owner: str | None,
    mismatch_message: str,
) -> str | None:
    """按 owner 返回可信 config_hash；缺失 owner 时直接失败。"""
    if owner is None:
        return None
    expected_config_hash = trusted_parameter_hashes.get(owner)
    if not expected_config_hash:
        raise ValueError(mismatch_message)
    return expected_config_hash


def _artifact_owner_computer(artifact_name: str) -> str | None:
    """把已知 artifact 名映射回其 parameter computer。"""
    return {
        "semantic_embeddings": "semantic_embedding_computer",
        "semantic_index": "semantic_duplicate_group_computer",
    }.get(artifact_name)


def _relation_owner_computer(relation_name: str) -> str | None:
    """把已知 relation 名映射回其 parameter computer。"""
    return {
        "semantic_duplicate_pairs": "semantic_duplicate_group_computer",
        "perceptual_duplicate_pairs": "perceptual_duplicate_group_computer",
    }.get(relation_name)
