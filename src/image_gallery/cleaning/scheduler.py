import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

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
                    config=step.config,
                    config_hash=step.config_hash,
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
            written_relation_paths = write_relation_tables(result.relation_updates, context.paths)
            relation_paths.update(written_relation_paths)
            self._write_relation_manifests(
                relation_updates=result.relation_updates,
                relation_paths=written_relation_paths,
                computer_name=step.computer_name,
                config_hash=step.config_hash,
            )

        return ParameterScheduleResult(
            tables=current_tables,
            artifact_paths=artifact_paths,
            relation_paths=relation_paths,
        )

    def _requires_image_batch(self, plan: ParameterExecutionPlan) -> bool:
        """判断计划中是否存在需要共享图片解码结果的 per-image computer。"""
        return any(step.execution_mode == ExecutionMode.PER_IMAGE for step in plan.steps)

    def _build_image_batch(self, context: CleanerRunContext, tables: CleaningTables) -> ImageBatch:
        """统一读取和解码当前 parameter_table 中的图片。"""
        items: list[ImageBatchItem] = []
        for row in tables.parameter_table.to_dict(orient="records"):
            image_id = str(row["image_id"])
            image_uri = str(row["image_uri"])
            try:
                # 每张图片只读取和解码一次，后续 per-image computer 共享同一个 ImageBatch。
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
        """校验 computer 实际产出了本步骤请求的全部参数列。"""
        missing_parameters = [
            parameter for parameter in sorted(step.requested_parameters) if parameter not in updates.columns
        ]
        if missing_parameters:
            raise ValueError(
                f"computer did not produce requested parameters: {step.computer_name} {missing_parameters}"
            )

    def _write_relation_manifests(
        self,
        relation_updates: dict[str, pd.DataFrame],
        relation_paths: dict[str, str],
        computer_name: str,
        config_hash: str,
    ) -> None:
        """为关系表写出最小 manifest，便于 resume/rerun 复用校验。"""
        created_at = datetime.now(timezone.utc).isoformat()
        for relation_name, frame in relation_updates.items():
            relation_path = Path(relation_paths[relation_name])
            manifest_path = relation_path.with_name(f"{relation_path.name}.manifest.json")
            artifact_refs = []
            if "artifact_ref" in frame.columns:
                artifact_refs = sorted(
                    {
                        value
                        for value in frame["artifact_ref"].fillna("").astype(str).tolist()
                        if value
                    }
                )
            payload = {
                "artifact_schema_version": 1,
                "relation_name": relation_name,
                "computer_name": computer_name,
                "config_hash": config_hash,
                "row_count": int(len(frame)),
                "artifact_refs": artifact_refs,
                "created_at": created_at,
            }
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
