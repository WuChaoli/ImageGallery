from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.cleaner import Cleaner
from image_gallery.cleaning.config import (
    OperatorConfigInput,
    ParsedOperatorConfig,
    merge_default_config,
    parse_operator_configs,
)
from image_gallery.cleaning.context import CleanerRunContext, create_run_context
from image_gallery.cleaning.errors import CleanerStateError
from image_gallery.cleaning.export import export_cleaning_result
from image_gallery.cleaning.preview import PreviewResult, apply_final_action, build_preview
from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore, OperatorRunState, build_state_frame
from image_gallery.cleaning.tables import (
    CleaningTables,
    initialize_evaluation_table,
    initialize_parameter_table,
    update_evaluation_columns,
    update_operator_outputs,
    update_parameter_columns,
    write_tables,
)
from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


@dataclass(frozen=True)
class ResolvedOperatorRun:
    """一次运行中已绑定 spec、backend 和配置的逻辑算子。"""

    parsed_config: ParsedOperatorConfig
    spec: OperatorSpec
    backend: BackendAdapter
    merged_config: dict[str, object]


class BasicCleaner(Cleaner):
    """基础图片清洗策略。"""

    def __init__(
        self,
        operator_configs: OperatorConfigInput,
        output_dir: str | Path | None = None,
        registry: OperatorRegistry | None = None,
    ) -> None:
        self._operator_configs = parse_operator_configs(operator_configs)
        self._registry = registry if registry is not None else create_default_registry()
        self._output_dir = output_dir
        self._context: CleanerRunContext | None = None
        self._tables: CleaningTables | None = None
        self._state: CleanerRunState | None = None

    def run(
        self,
        dataset: Dataset,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> "BasicCleaner":
        """执行全部启用算子，并写出清洗产物。"""
        selected_output_dir = output_dir if output_dir is not None else self._output_dir
        context = create_run_context(dataset, "basic", self._operator_configs, selected_output_dir)
        if context.paths.run_dir.exists() and not overwrite:
            raise CleanerStateError(f"run output already exists: {context.paths.run_dir}")

        parameter_table = initialize_parameter_table(dataset)
        evaluation_table = initialize_evaluation_table(parameter_table)
        tables = CleaningTables(parameter_table=parameter_table, evaluation_table=evaluation_table, operator_outputs={})
        self._context = context
        self._tables = tables

        resolved_runs = self._resolve_operator_configs(self._operator_configs)
        artifact_paths: dict[str, str] = {}
        operator_states: list[OperatorRunState] = []

        for backend, backend_runs in self._group_by_backend(resolved_runs).values():
            backend_result = self._run_backend_group(backend, backend_runs)
            tables = CleaningTables(
                parameter_table=update_parameter_columns(tables.parameter_table, backend_result.parameter_updates),
                evaluation_table=tables.evaluation_table,
                operator_outputs=tables.operator_outputs,
            )
            artifact_paths.update(backend_result.artifact_refs)
            self._tables = tables

        for resolved_run in resolved_runs:
            operator_states.append(self._evaluate_operator(resolved_run))
            _, tables, _ = self._require_run(allow_missing_state=True)

        tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=apply_final_action(tables.evaluation_table, tables.operator_outputs),
            operator_outputs=tables.operator_outputs,
        )
        self._tables = tables
        state = self._build_state(context, resolved_runs, operator_states, artifact_paths, "completed")
        self._state = state
        write_tables(tables, context.paths)
        JsonRunStateStore().save(state, context.paths.state_path)
        return self

    def preview(self, limit: int = 20) -> PreviewResult:
        """返回当前评估宽表的预览摘要。"""
        _, tables, _ = self._require_run()
        return build_preview(tables.evaluation_table, tables.operator_outputs, limit=limit)

    def state(self) -> pd.DataFrame:
        """返回算子级状态矩阵。"""
        _, _, state = self._require_run()
        return build_state_frame(state)

    def config(self, operator_configs: OperatorConfigInput) -> "BasicCleaner":
        """更新算子配置，并把相关算子状态标记为 stale。"""
        parsed_configs = parse_operator_configs(operator_configs)
        self._operator_configs = self._replace_operator_configs(parsed_configs)
        if self._state is None:
            return self

        resolved_runs = self._resolve_operator_configs(parsed_configs)
        stale_names = {run.spec.name for run in resolved_runs}
        operator_config_hashes = dict(self._state.operator_config_hashes)
        for run in resolved_runs:
            operator_config_hashes[run.spec.name] = run.parsed_config.config_hash
        self._state = replace(
            self._state,
            enabled_operator_configs=self._enabled_operator_configs_from_current(),
            operator_config_hashes=operator_config_hashes,
            operator_states=[
                replace(operator_state, status="stale")
                if operator_state.operator_name in stale_names
                else operator_state
                for operator_state in self._state.operator_states
            ],
            status="stale",
        )
        self._save_current_outputs()
        return self

    def rerun(self, operator_configs: OperatorConfigInput) -> "BasicCleaner":
        """按传入配置重新执行指定算子。"""
        self._require_run()
        parsed_configs = parse_operator_configs(operator_configs)
        self._operator_configs = self._replace_operator_configs(parsed_configs)
        resolved_runs = self._resolve_operator_configs(parsed_configs)
        artifact_paths: dict[str, str] = {}
        operator_states: list[OperatorRunState] = []

        backend_runs_to_execute = self._runs_requiring_parameters(resolved_runs)
        for backend, backend_runs in self._group_by_backend(backend_runs_to_execute).values():
            backend_result = self._run_backend_group(backend, backend_runs)
            _, tables, _ = self._require_run()
            self._tables = CleaningTables(
                parameter_table=update_parameter_columns(tables.parameter_table, backend_result.parameter_updates),
                evaluation_table=tables.evaluation_table,
                operator_outputs=tables.operator_outputs,
            )
            artifact_paths.update(backend_result.artifact_refs)

        for resolved_run in resolved_runs:
            operator_states.append(self._evaluate_operator(resolved_run))

        context, tables, state = self._require_run()
        rerun_names = {operator_state.operator_name for operator_state in operator_states}
        state_by_name = {operator_state.operator_name: operator_state for operator_state in state.operator_states}
        for operator_state in operator_states:
            state_by_name[operator_state.operator_name] = operator_state
        ordered_states = [
            state_by_name[operator_state.operator_name]
            if operator_state.operator_name in rerun_names
            else operator_state
            for operator_state in state.operator_states
        ]
        for operator_state in operator_states:
            if operator_state.operator_name not in {existing.operator_name for existing in state.operator_states}:
                ordered_states.append(operator_state)

        tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=apply_final_action(tables.evaluation_table, tables.operator_outputs),
            operator_outputs=tables.operator_outputs,
        )
        self._tables = tables
        operator_config_hashes = dict(state.operator_config_hashes)
        for resolved_run in resolved_runs:
            operator_config_hashes[resolved_run.spec.name] = resolved_run.parsed_config.config_hash
        self._state = replace(
            state,
            enabled_operator_configs=self._enabled_operator_configs_from_current(),
            operator_config_hashes=operator_config_hashes,
            artifact_paths={**state.artifact_paths, **artifact_paths},
            status="completed",
            operator_states=ordered_states,
        )
        self._save_current_outputs()
        return self

    def result(self, operator_name: str) -> pd.DataFrame:
        """返回 image_id、image_uri 和该算子拥有的输出列。"""
        _, tables, _ = self._require_run()
        if operator_name not in tables.operator_outputs:
            raise CleanerStateError(f"operator has no result: {operator_name}")
        columns = ["image_id", "image_uri", *tables.operator_outputs[operator_name]]
        return tables.evaluation_table[columns].copy()

    def export(self, kind: str, path: str) -> Dataset:
        """导出清洗视图为 Dataset。"""
        _, tables, _ = self._require_run()
        return export_cleaning_result(kind, tables, path)

    def _resolve_operator_configs(
        self,
        parsed_configs: list[ParsedOperatorConfig],
    ) -> list[ResolvedOperatorRun]:
        """解析算子配置，绑定 OperatorSpec、BackendAdapter 和合并后配置。"""
        resolved: list[ResolvedOperatorRun] = []
        for parsed_config in parsed_configs:
            spec, backend = self._registry.resolve(parsed_config.operator_name)
            merged_config = merge_default_config(parsed_config, spec.default_config)
            resolved.append(
                ResolvedOperatorRun(
                    parsed_config=merged_config,
                    spec=spec,
                    backend=backend,
                    merged_config=merged_config.config,
                )
            )
        return resolved

    def _group_by_backend(
        self,
        runs: list[ResolvedOperatorRun],
    ) -> dict[str, tuple[BackendAdapter, list[ResolvedOperatorRun]]]:
        """把已解析算子按 backend_name 分组。"""
        grouped: dict[str, tuple[BackendAdapter, list[ResolvedOperatorRun]]] = {}
        for run in runs:
            if run.backend.name not in grouped:
                grouped[run.backend.name] = (run.backend, [])
            grouped[run.backend.name][1].append(run)
        return grouped

    def _run_backend_group(self, backend: BackendAdapter, runs: list[ResolvedOperatorRun]) -> BackendResult:
        """一次执行同一后端下的多个逻辑算子参数计算。"""
        context, tables, _ = self._require_run(allow_missing_state=True)
        requests = [
            BackendOperatorRequest(
                operator_name=run.spec.name,
                parameter_columns=run.spec.parameter_columns,
                config=run.merged_config,
                config_hash=run.parsed_config.config_hash,
            )
            for run in runs
        ]
        return backend.compute_parameters(
            context.dataset,
            tables.parameter_table,
            requests,
            context.paths.artifacts_dir,
        )

    def _evaluate_operator(self, run: ResolvedOperatorRun) -> OperatorRunState:
        """基于参数表执行单个逻辑算子的评估，并更新 evaluation_table 和 manifest。"""
        _, tables, _ = self._require_run(allow_missing_state=True)
        updates = run.spec.evaluate(tables.parameter_table, run.merged_config)
        operator_outputs = update_operator_outputs(tables.operator_outputs, run.spec.name, run.spec.evaluation_columns)
        evaluation_table = update_evaluation_columns(
            tables.evaluation_table,
            updates,
            run.spec.evaluation_columns,
        )
        self._tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=evaluation_table,
            operator_outputs=operator_outputs,
        )
        return OperatorRunState(
            operator_name=run.spec.name,
            config_hash=run.parsed_config.config_hash,
            status="completed",
            parameter_columns=run.spec.parameter_columns,
            evaluation_columns=run.spec.evaluation_columns,
            processed_count=len(tables.parameter_table),
            skipped_count=0,
            failed_count=0,
        )

    def _require_run(
        self,
        allow_missing_state: bool = False,
    ) -> tuple[CleanerRunContext, CleaningTables, CleanerRunState]:
        """确认 Cleaner 已经 run，并返回内部状态。"""
        if self._context is None or self._tables is None:
            raise CleanerStateError("BasicCleaner has not been run")
        if self._state is None:
            if allow_missing_state:
                empty_state = CleanerRunState(
                    run_id=self._context.run_id,
                    dataset_fingerprint=self._context.dataset_fingerprint,
                    cleaner_type=self._context.cleaner_type,
                    enabled_operator_configs=[],
                    operator_config_hashes={},
                    parameter_table_path=str(self._context.paths.parameter_table_path),
                    evaluation_table_path=str(self._context.paths.evaluation_table_path),
                    operator_outputs_path=str(self._context.paths.operator_outputs_path),
                    artifact_paths={},
                    status="running",
                    operator_states=[],
                )
                return self._context, self._tables, empty_state
            raise CleanerStateError("BasicCleaner run has not completed")
        return self._context, self._tables, self._state

    def _build_state(
        self,
        context: CleanerRunContext,
        resolved_runs: list[ResolvedOperatorRun],
        operator_states: list[OperatorRunState],
        artifact_paths: dict[str, str],
        status: str,
    ) -> CleanerRunState:
        """构造当前 run 的状态快照。"""
        return CleanerRunState(
            run_id=context.run_id,
            dataset_fingerprint=context.dataset_fingerprint,
            cleaner_type=context.cleaner_type,
            enabled_operator_configs=[{run.spec.name: run.merged_config} for run in resolved_runs],
            operator_config_hashes={run.spec.name: run.parsed_config.config_hash for run in resolved_runs},
            parameter_table_path=str(context.paths.parameter_table_path),
            evaluation_table_path=str(context.paths.evaluation_table_path),
            operator_outputs_path=str(context.paths.operator_outputs_path),
            artifact_paths=artifact_paths,
            status=status,
            operator_states=operator_states,
        )

    def _runs_requiring_parameters(self, runs: list[ResolvedOperatorRun]) -> list[ResolvedOperatorRun]:
        """筛选当前参数表缺少字段、需要执行 backend 的算子。"""
        _, tables, _ = self._require_run()
        existing_columns = set(tables.parameter_table.columns)
        return [
            run
            for run in runs
            if any(parameter_column not in existing_columns for parameter_column in run.spec.parameter_columns)
        ]

    def _replace_operator_configs(
        self,
        parsed_configs: list[ParsedOperatorConfig],
    ) -> list[ParsedOperatorConfig]:
        """替换当前运行配置中的指定算子配置。"""
        replacements = {config.operator_name: config for config in parsed_configs}
        replaced_names: set[str] = set()
        updated: list[ParsedOperatorConfig] = []
        for existing_config in self._operator_configs:
            replacement = replacements.get(existing_config.operator_name)
            if replacement is None:
                updated.append(existing_config)
                continue
            updated.append(replacement)
            replaced_names.add(existing_config.operator_name)
        for parsed_config in parsed_configs:
            if parsed_config.operator_name not in replaced_names:
                updated.append(parsed_config)
        return updated

    def _enabled_operator_configs_from_current(self) -> list[dict[str, dict[str, object]]]:
        """把当前算子配置转回 state 使用的输入形态。"""
        resolved_runs = self._resolve_operator_configs(self._operator_configs)
        return [{run.spec.name: run.merged_config} for run in resolved_runs]

    def _save_current_outputs(self) -> None:
        """保存当前表和状态。"""
        context, tables, state = self._require_run()
        write_tables(tables, context.paths)
        JsonRunStateStore().save(state, context.paths.state_path)
