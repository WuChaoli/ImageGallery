from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.cleaner import Cleaner
from image_gallery.cleaning.config import OperatorConfigInput, ParsedOperatorConfig, parse_operator_configs
from image_gallery.cleaning.context import CleanerRunContext, create_run_context
from image_gallery.cleaning.errors import CleanerStateError
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.export import export_cleaning_result
from image_gallery.cleaning.html_preview import PreviewHtmlOptions, build_preview_frame, write_preview_html
from image_gallery.cleaning.planner import CleaningRunPlanner, CompiledCleaningPlan, ResolvedOperatorRun
from image_gallery.cleaning.preview import PreviewResult, apply_final_action, build_preview
from image_gallery.cleaning.scheduler import ParameterScheduler
from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore, OperatorRunState, build_state_frame
from image_gallery.cleaning.tables import (
    CleaningTables,
    initialize_evaluation_table,
    initialize_parameter_table,
    write_tables,
)
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider


class BasicCleaner(Cleaner):
    """基础图片清洗策略。"""

    def __init__(
        self,
        operator_configs: OperatorConfigInput,
        output_dir: str | Path | None = None,
        registry: OperatorRegistry | None = None,
        semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
    ) -> None:
        self._operator_configs = parse_operator_configs(operator_configs)
        self._registry = registry if registry is not None else create_default_registry(semantic_providers)
        self._output_dir = output_dir
        self._context: CleanerRunContext | None = None
        self._tables: CleaningTables | None = None
        self._state: CleanerRunState | None = None
        self._compiled_plan: CompiledCleaningPlan | None = None

    def compile(self) -> "BasicCleaner":
        """编译当前算子配置并缓存执行计划。"""
        self._compiled_plan = CleaningRunPlanner(self._registry).compile(self._operator_configs)
        return self

    def plan(self) -> pd.DataFrame:
        """返回当前参数计算计划。"""
        compiled_plan = self._require_compiled_plan()
        return compiled_plan.parameter_plan.to_frame()

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
        tables = CleaningTables(
            parameter_table=parameter_table,
            evaluation_table=evaluation_table,
            operator_outputs={},
            parameter_manifest={},
        )
        self._context = context
        self._tables = tables

        compiled_plan = self._require_compiled_plan()
        operator_states: list[OperatorRunState] = []

        started_at = _utc_now()
        schedule_result = ParameterScheduler(self._registry).run(compiled_plan.parameter_plan, context, tables)
        tables = schedule_result.tables
        self._tables = tables

        evaluator = OperatorEvaluator()
        for resolved_run in compiled_plan.resolved_operator_runs:
            tables, operator_state = evaluator.evaluate(resolved_run, tables)
            self._tables = tables
            operator_states.append(operator_state)

        artifact_paths = schedule_result.artifact_paths
        relation_paths = schedule_result.relation_paths
        resolved_runs = list(compiled_plan.resolved_operator_runs)

        tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=apply_final_action(tables.evaluation_table, tables.operator_outputs),
            operator_outputs=tables.operator_outputs,
            parameter_manifest=tables.parameter_manifest,
        )
        self._tables = tables
        state = self._build_state(
            context,
            resolved_runs,
            operator_states,
            artifact_paths,
            relation_paths,
            "completed",
            started_at,
        )
        self._state = state
        write_tables(tables, context.paths)
        JsonRunStateStore().save(state, context.paths.state_path)
        return self

    def preview(self, limit: int = 20) -> PreviewResult:
        """返回当前评估宽表的预览摘要。"""
        _, tables, _ = self._require_run()
        return build_preview(tables.evaluation_table, tables.operator_outputs, limit=limit)

    def preview_html(
        self,
        path: str | Path,
        *,
        action: str | None = None,
        filters: dict[str, object] | None = None,
        groupby: str | None = None,
        include_group_context: bool = False,
        sort_by: list[str] | None = None,
        ascending: bool | list[bool] = True,
        caption_columns: list[str] | None = None,
        max_rows: int = 200,
        max_groups: int = 50,
        max_items_per_group: int = 20,
        thumbnail_size: int = 320,
        columns_per_row: int = 6,
    ) -> Path:
        """把当前清洗结果写出为静态 HTML 预览页。"""
        context, tables, _ = self._require_run()
        options = PreviewHtmlOptions(
            action=action,
            filters=filters,
            groupby=groupby,
            include_group_context=include_group_context,
            sort_by=sort_by,
            ascending=ascending,
            caption_columns=caption_columns,
            max_rows=max_rows,
            max_groups=max_groups,
            max_items_per_group=max_items_per_group,
            thumbnail_size=thumbnail_size,
            columns_per_row=columns_per_row,
        )
        frame = build_preview_frame(
            tables.evaluation_table,
            action=action,
            filters=filters,
            groupby=groupby,
            include_group_context=include_group_context,
            sort_by=sort_by,
            ascending=ascending,
            max_rows=max_rows,
        )
        return write_preview_html(frame, path, dataset=context.dataset, options=options)

    def state(self) -> pd.DataFrame:
        """返回算子级状态矩阵。"""
        _, _, state = self._require_run()
        return build_state_frame(state)

    def config(self, operator_configs: OperatorConfigInput) -> "BasicCleaner":
        """更新算子配置，并把相关算子状态标记为 stale。"""
        parsed_configs = parse_operator_configs(operator_configs)
        self._operator_configs = self._replace_operator_configs(parsed_configs)
        self._compiled_plan = None
        if self._state is None:
            return self

        resolved_runs = CleaningRunPlanner(self._registry).compile(parsed_configs).resolved_operator_runs
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
        self._compiled_plan = None
        resolved_runs = CleaningRunPlanner(self._registry).compile(parsed_configs).resolved_operator_runs
        operator_states: list[OperatorRunState] = []

        _, tables, _ = self._require_run()
        evaluator = OperatorEvaluator()
        for resolved_run in resolved_runs:
            tables, operator_state = evaluator.evaluate(resolved_run, tables)
            self._tables = tables
            operator_states.append(operator_state)

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
            parameter_manifest=tables.parameter_manifest,
        )
        self._tables = tables
        operator_config_hashes = dict(state.operator_config_hashes)
        for resolved_run in resolved_runs:
            operator_config_hashes[resolved_run.spec.name] = resolved_run.parsed_config.config_hash
        self._state = replace(
            state,
            enabled_operator_configs=self._enabled_operator_configs_from_current(),
            operator_config_hashes=operator_config_hashes,
            artifact_paths=state.artifact_paths,
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

    def _require_compiled_plan(self) -> CompiledCleaningPlan:
        """返回已编译计划；不存在时自动编译。"""
        if self._compiled_plan is None:
            self.compile()
        if self._compiled_plan is None:
            raise CleanerStateError("BasicCleaner compile failed")
        return self._compiled_plan

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
                    parameter_config_hashes={},
                    parameter_table_path=str(self._context.paths.parameter_table_path),
                    evaluation_table_path=str(self._context.paths.evaluation_table_path),
                    operator_outputs_path=str(self._context.paths.operator_outputs_path),
                    parameter_manifest_path=str(self._context.paths.parameter_manifest_path),
                    relation_paths={},
                    artifact_paths={},
                    started_at="",
                    finished_at="",
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
        relation_paths: dict[str, str],
        status: str,
        started_at: str,
    ) -> CleanerRunState:
        """构造当前 run 的状态快照。"""
        _, tables, _ = self._require_run(allow_missing_state=True)
        return CleanerRunState(
            run_id=context.run_id,
            dataset_fingerprint=context.dataset_fingerprint,
            cleaner_type=context.cleaner_type,
            enabled_operator_configs=[{run.spec.name: run.merged_config} for run in resolved_runs],
            operator_config_hashes={run.spec.name: run.parsed_config.config_hash for run in resolved_runs},
            parameter_config_hashes={
                parameter: str(manifest.get("config_hash", ""))
                for parameter, manifest in tables.parameter_manifest.items()
            },
            parameter_table_path=str(context.paths.parameter_table_path),
            evaluation_table_path=str(context.paths.evaluation_table_path),
            operator_outputs_path=str(context.paths.operator_outputs_path),
            parameter_manifest_path=str(context.paths.parameter_manifest_path),
            relation_paths=relation_paths,
            artifact_paths=artifact_paths,
            started_at=started_at,
            finished_at=_utc_now(),
            status=status,
            operator_states=operator_states,
        )

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
        resolved_runs = CleaningRunPlanner(self._registry).compile(self._operator_configs).resolved_operator_runs
        return [{run.spec.name: run.merged_config} for run in resolved_runs]

    def _save_current_outputs(self) -> None:
        """保存当前表和状态。"""
        context, tables, state = self._require_run()
        write_tables(tables, context.paths)
        JsonRunStateStore().save(state, context.paths.state_path)


def _utc_now() -> str:
    """返回 UTC ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()
