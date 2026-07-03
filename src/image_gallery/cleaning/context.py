import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from image_gallery.cleaning.config import ParsedOperatorConfig
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class CleanerRunPaths:
    """一次清洗运行的产物路径集合。"""

    run_dir: Path
    parameter_table_path: Path
    evaluation_table_path: Path
    operator_outputs_path: Path
    relations_dir: Path
    artifacts_dir: Path
    state_path: Path


@dataclass(frozen=True)
class CleanerRunContext:
    """一次清洗运行的上下文。"""

    run_id: str
    dataset: Dataset
    dataset_fingerprint: str
    cleaner_type: str
    operator_configs: list[ParsedOperatorConfig]
    paths: CleanerRunPaths


def create_run_context(
    dataset: Dataset,
    cleaner_type: str,
    operator_configs: list[ParsedOperatorConfig],
    output_dir: str | Path | None,
) -> CleanerRunContext:
    """创建 run_id、产物目录和运行上下文。"""
    run_id = _new_run_id()
    root_dir = Path(output_dir) if output_dir is not None else Path("cleaning_outputs")
    paths = build_run_paths(root_dir / run_id)
    return CleanerRunContext(
        run_id=run_id,
        dataset=dataset,
        dataset_fingerprint=dataset.fingerprint(),
        cleaner_type=cleaner_type,
        operator_configs=operator_configs,
        paths=paths,
    )


def build_run_paths(run_dir: Path) -> CleanerRunPaths:
    """根据 run_dir 生成全部约定路径。"""
    return CleanerRunPaths(
        run_dir=run_dir,
        parameter_table_path=run_dir / "parameter_table.parquet",
        evaluation_table_path=run_dir / "evaluation_table.parquet",
        operator_outputs_path=run_dir / "operator_outputs.yaml",
        relations_dir=run_dir / "relations",
        artifacts_dir=run_dir / "artifacts",
        state_path=run_dir / "state.json",
    )


def _new_run_id() -> str:
    """生成带时间前缀的清洗 run_id。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"
