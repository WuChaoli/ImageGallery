"""CleanerResult 使用的文件复制与调试包导出实现。"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from image_gallery.cleaning._result_artifacts import ResultArtifacts
from image_gallery.cleaning.state import JsonRunStateStore


def export_table(artifacts: ResultArtifacts, kind: str, path: Path | str) -> Path:
    """把某张运行表拷贝到目标路径。"""
    kind_map = {
        "parameter": "parameter_table.parquet",
        "parameters": "parameter_table.parquet",
        "evaluation": "evaluation_table.parquet",
        "evaluations": "evaluation_table.parquet",
        "full": "evaluation_table.parquet",
    }
    normalized = kind.strip().lower()
    if normalized not in kind_map:
        raise ValueError(f"unsupported export_table kind: {kind}")
    return _copy_file(artifacts.table_file(kind_map[normalized]), Path(path))


def export_manifest(artifacts: ResultArtifacts, kind: str, path: Path | str) -> Path:
    """导出指定运行时 manifest。"""
    normalized = kind.strip().lower()
    if normalized not in {"execution_plan", "artifacts"}:
        raise ValueError(f"unsupported manifest kind: {kind}")
    source = artifacts.run_dir() / "manifests" / f"{normalized}.json"
    if not source.exists():
        raise FileNotFoundError(f"manifest file missing: {normalized}")
    return _copy_file(source, Path(path))


def export_relation(artifacts: ResultArtifacts, relation_name: str, path: Path | str) -> Path:
    """把指定 relation 表复制到用户路径。"""
    state_path = artifacts.run_dir() / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"state file missing: {state_path.name}")
    relation_path = JsonRunStateStore().load(state_path).relation_paths.get(relation_name)
    if relation_path is None:
        raise KeyError(f"unknown relation_name: {relation_name}")

    source = Path(relation_path)
    if not source.exists():
        raise FileNotFoundError(f"relation table missing: {relation_name}")
    return _copy_file(source, Path(path))


def export_debug_bundle(artifacts: ResultArtifacts, path: Path | str) -> Path:
    """导出包含表、manifest、状态和 relation 副本的调试包。"""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_dir = artifacts.run_dir()
    run_paths = artifacts.run_paths()
    with zipfile.ZipFile(destination, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_name, source in (
            ("tables/parameter_table.parquet", artifacts.table_file("parameter_table.parquet")),
            ("tables/evaluation_table.parquet", artifacts.table_file("evaluation_table.parquet")),
            ("manifests/operator_outputs.json", run_paths.operator_outputs_path),
            ("manifests/parameter_manifest.json", run_paths.parameter_manifest_path),
            ("manifests/execution_plan.json", run_dir / "manifests" / "execution_plan.json"),
            ("manifests/artifacts.json", run_dir / "manifests" / "artifacts.json"),
            ("state.json", run_dir / "state.json"),
        ):
            if source.exists():
                archive.write(source, archive_name)

        state_path = run_dir / "state.json"
        if state_path.exists():
            state = JsonRunStateStore().load(state_path)
            for relation_name, relation_path in sorted(state.relation_paths.items()):
                source = Path(relation_path)
                if source.exists():
                    archive.write(source, f"relations/{relation_name}.parquet")
                manifest_path = source.with_name(f"{source.name}.manifest.json")
                if manifest_path.exists():
                    archive.write(manifest_path, f"relations/{relation_name}.parquet.manifest.json")
    return destination


def _copy_file(source: Path, destination: Path) -> Path:
    """创建目标父目录并保留元数据复制文件。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination
