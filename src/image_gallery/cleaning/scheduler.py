from dataclasses import dataclass
from io import BytesIO

import pandas as pd
from PIL import Image

from image_gallery.cleaning.context import CleanerRunContext
from image_gallery.cleaning.planner import ParameterExecutionPlan, ParameterExecutionStep
from image_gallery.cleaning.tables import CleaningTables, update_parameter_columns, write_relation_tables
from image_gallery.operators.computers.base import ExecutionMode, ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.registry import OperatorRegistry


@dataclass(frozen=True)
class ParameterScheduleResult:
    """参数计算调度结果。"""

    tables: CleaningTables
    artifact_paths: dict[str, str]
    relation_paths: dict[str, str]


class ParameterScheduler:
    """按已编译计划执行参数计算单元。"""

    def __init__(self, registry: OperatorRegistry) -> None:
        self._registry = registry

    def run(
        self,
        plan: ParameterExecutionPlan,
        context: CleanerRunContext,
        tables: CleaningTables,
    ) -> ParameterScheduleResult:
        """执行参数计划，并返回更新后的 tables 和产物路径。"""
        artifact_paths: dict[str, str] = {}
        relation_paths: dict[str, str] = {}
        image_batch = self._build_image_batch(context, tables) if self._requires_image_batch(plan) else None
        current_tables = tables

        for step in plan.steps:
            computer = self._registry.get_parameter_computer(step.computer_name)
            result = computer.compute(
                ParameterRequest(
                    parameter_table=current_tables.parameter_table,
                    requested_parameters=step.requested_parameters,
                    config={},
                    config_hash="default",
                    artifacts_dir=context.paths.artifacts_dir,
                    image_batch=image_batch if step.execution_mode == ExecutionMode.PER_IMAGE else None,
                )
            )
            self._require_requested_parameters(step, result.parameter_updates)
            current_tables = CleaningTables(
                parameter_table=update_parameter_columns(current_tables.parameter_table, result.parameter_updates),
                evaluation_table=current_tables.evaluation_table,
                operator_outputs=current_tables.operator_outputs,
                parameter_manifest={**current_tables.parameter_manifest, **result.parameter_manifest},
            )
            artifact_paths.update(result.artifact_refs)
            relation_paths.update(write_relation_tables(result.relation_updates, context.paths))

        return ParameterScheduleResult(
            tables=current_tables,
            artifact_paths=artifact_paths,
            relation_paths=relation_paths,
        )

    def _requires_image_batch(self, plan: ParameterExecutionPlan) -> bool:
        return any(step.execution_mode == ExecutionMode.PER_IMAGE for step in plan.steps)

    def _build_image_batch(self, context: CleanerRunContext, tables: CleaningTables) -> ImageBatch:
        """统一读取和解码当前 parameter_table 中的图片。"""
        items: list[ImageBatchItem] = []
        for row in tables.parameter_table.to_dict(orient="records"):
            image_id = str(row["image_id"])
            image_uri = str(row["image_uri"])
            try:
                data = context.dataset.read_image_bytes(image_uri)
                with Image.open(BytesIO(data)) as opened:
                    opened.load()
                    image = opened.copy()
                    image.format = opened.format
                items.append(ImageBatchItem(image_id, image_uri, row, data, image, None))
            except Exception as exc:
                items.append(ImageBatchItem(image_id, image_uri, row, None, None, str(exc)))
        return ImageBatch(items=items)

    def _require_requested_parameters(self, step: ParameterExecutionStep, updates: pd.DataFrame) -> None:
        missing_parameters = [
            parameter for parameter in sorted(step.requested_parameters) if parameter not in updates.columns
        ]
        if missing_parameters:
            raise ValueError(
                f"computer did not produce requested parameters: {step.computer_name} {missing_parameters}"
            )
