import json
from dataclasses import dataclass
from typing import cast

import pandas as pd

from image_gallery.cleaning._dataset_compat import normalize_identifier_columns
from image_gallery.cleaning.context import CleanerRunPaths
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class CleaningTables:
    """一次清洗运行的两张主表、算子输出列和参数 manifest。"""

    parameter_table: pd.DataFrame
    evaluation_table: pd.DataFrame
    operator_outputs: dict[str, list[str]]
    parameter_manifest: dict[str, dict[str, object]]


def initialize_parameter_table(dataset: Dataset) -> pd.DataFrame:
    """从 raw Dataset 初始化 parameter_table。"""
    frame = normalize_identifier_columns(dataset.to_frame())
    if "image_id" not in frame.columns:
        raise ValueError("missing required columns: ['image_id']")
    if hasattr(dataset, "read_image_bytes") and "image_uri" not in frame.columns:
        raise ValueError("missing required columns: ['image_uri']")
    if "image_uri" not in frame.columns:
        frame["image_uri"] = frame["image_id"].astype(str)
    columns = ["image_id", "image_uri"]
    if "source_uri" in frame.columns:
        columns.append("source_uri")
    return cast(pd.DataFrame, frame[columns]).copy()


def initialize_evaluation_table(parameter_table: pd.DataFrame) -> pd.DataFrame:
    """从 parameter_table 初始化 evaluation_table 的基础列。"""
    _require_columns(parameter_table, ["image_id", "image_uri"])
    evaluation_table = cast(pd.DataFrame, parameter_table[["image_id", "image_uri"]].copy())
    evaluation_table["final_action"] = "keep"
    evaluation_table["final_reason"] = ""
    evaluation_table["triggered_operator_names"] = ""
    return evaluation_table


def read_tables(paths: CleanerRunPaths) -> CleaningTables:
    """从磁盘读取 parameter_table、evaluation_table 和 manifest。"""
    operator_outputs = json.loads(paths.operator_outputs_path.read_text(encoding="utf-8"))
    parameter_manifest = json.loads(paths.parameter_manifest_path.read_text(encoding="utf-8"))
    return CleaningTables(
        parameter_table=pd.read_parquet(paths.parameter_table_path),
        evaluation_table=pd.read_parquet(paths.evaluation_table_path),
        operator_outputs={key: list(value) for key, value in operator_outputs.items()},
        parameter_manifest={key: dict(value) for key, value in parameter_manifest.items()},
    )


def write_tables(tables: CleaningTables, paths: CleanerRunPaths) -> None:
    """把两张主表、operator_outputs 和 parameter_manifest 写入磁盘。"""
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.parameter_table_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifests_dir.mkdir(parents=True, exist_ok=True)
    paths.relations_dir.mkdir(parents=True, exist_ok=True)
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    tables.parameter_table.to_parquet(paths.parameter_table_path, index=False)
    tables.evaluation_table.to_parquet(paths.evaluation_table_path, index=False)
    paths.operator_outputs_path.write_text(
        json.dumps(tables.operator_outputs, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    paths.parameter_manifest_path.write_text(
        json.dumps(tables.parameter_manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_relation_tables(
    relation_updates: dict[str, pd.DataFrame],
    paths: CleanerRunPaths,
) -> dict[str, str]:
    """把 relation 表写入 relations 目录并返回 relation 名称到路径的映射。"""
    paths.relations_dir.mkdir(parents=True, exist_ok=True)
    relation_paths: dict[str, str] = {}
    for relation_name, frame in relation_updates.items():
        relation_path = paths.relations_dir / f"{relation_name}.parquet"
        frame.to_parquet(relation_path, index=False)
        relation_paths[relation_name] = str(relation_path)
    return relation_paths


def update_parameter_columns(
    parameter_table: pd.DataFrame,
    updates: pd.DataFrame,
    key: str = "image_id",
) -> pd.DataFrame:
    """按 image_id 把后端产出的参数列合并进 parameter_table。"""
    _require_columns(parameter_table, [key])
    _require_columns(updates, [key])
    update_columns = [column for column in updates.columns if column != key]
    existing_update_columns = [column for column in update_columns if column in parameter_table]
    result = parameter_table.drop(columns=existing_update_columns, errors="ignore")
    return result.merge(updates[[key, *update_columns]], on=key, how="left")


def update_evaluation_columns(
    evaluation_table: pd.DataFrame,
    updates: pd.DataFrame,
    output_columns: list[str],
    key: str = "image_id",
) -> pd.DataFrame:
    """按 image_id 覆盖指定算子的评估输出列。"""
    _require_columns(evaluation_table, [key])
    _require_columns(updates, [key])
    unexpected_columns = [column for column in updates.columns if column not in {key, *output_columns}]
    if unexpected_columns:
        raise ValueError(f"unexpected evaluation columns: {unexpected_columns}")

    existing_output_columns = [column for column in output_columns if column in evaluation_table.columns]
    result = evaluation_table.drop(columns=existing_output_columns)
    prepared_updates = updates[[key, *[column for column in output_columns if column in updates.columns]]].copy()
    for column in output_columns:
        if column not in prepared_updates.columns:
            prepared_updates[column] = pd.NA
    return result.merge(cast(pd.DataFrame, prepared_updates[[key, *output_columns]]), on=key, how="left")


def update_operator_outputs(
    operator_outputs: dict[str, list[str]],
    operator_name: str,
    output_columns: list[str],
) -> dict[str, list[str]]:
    """记录某个算子拥有的 evaluation_table 输出列。"""
    owner_by_column: dict[str, str] = {}
    for existing_operator, columns in operator_outputs.items():
        if existing_operator == operator_name:
            continue
        for column in columns:
            owner_by_column[column] = existing_operator

    conflicts = [column for column in output_columns if column in owner_by_column]
    if conflicts:
        raise ValueError(f"columns already owned by another operator: {conflicts}")

    updated = {key: list(value) for key, value in operator_outputs.items()}
    updated[operator_name] = list(output_columns)
    return updated


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    """确认 DataFrame 包含必需列。"""
    missing_columns = [column for column in columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"missing required columns: {missing_columns}")
