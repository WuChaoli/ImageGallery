"""Artifact 持久化与 manifest 管理。"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ArtifactManifest:
    """落盘 Artifact 的描述信息。"""

    artifact_id: str
    artifact_type: str
    uri: str
    status: str
    owner_node_id: str
    schema_version: int
    schema_hash: str
    config_hash: str
    policy_hash: str
    row_count: int
    part_files: list[str]
    checksum: str
    created_at: str
    commit_marker: str
    manifest_uri: str

    @classmethod
    def from_path(cls, path: Path) -> ArtifactManifest:
        """从 manifest 文件反序列化。"""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            artifact_id=str(payload["artifact_id"]),
            artifact_type=str(payload["artifact_type"]),
            uri=str(payload["uri"]),
            status=str(payload["status"]),
            owner_node_id=str(payload["owner_node_id"]),
            schema_version=int(payload["schema_version"]),
            schema_hash=str(payload["schema_hash"]),
            config_hash=str(payload["config_hash"]),
            policy_hash=str(payload["policy_hash"]),
            row_count=int(payload["row_count"]),
            part_files=list(payload["part_files"]),
            checksum=str(payload["checksum"]),
            created_at=str(payload["created_at"]),
            commit_marker=str(payload["commit_marker"]),
            manifest_uri=str(payload.get("manifest_uri", path)),
        )


class ArtifactManager:
    """Artifact 提交与 manifest 验证器。"""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)

    def commit_dataframe_artifact(
        self,
        artifact_id: str,
        artifact_type: str,
        owner_node_id: str,
        frame: pd.DataFrame,
        relative_path: str,
        config_hash: str,
        policy_hash: str,
    ) -> ArtifactManifest:
        """提交 DataFrame 为 parquet，并返回可审计 manifest。"""
        self._validate_relative_path(relative_path)
        target = self._resolve_path(f"committed/{relative_path}")
        tmp_target = self._resolve_path(f"tmp/{relative_path}")
        tmp_target.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(tmp_target, index=False)
        checksum = _checksum_file(tmp_target)
        if target.exists():
            target.unlink()
        shutil.move(str(tmp_target), str(target))
        _cleanup_empty_parents(tmp_target.parent, self._resolve_path("tmp"))
        checksum = _checksum_file(target)
        manifest_path = target.with_name(f"{target.name}.manifest.json")
        manifest = ArtifactManifest(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            uri=str(target.resolve()),
            status="committed",
            owner_node_id=owner_node_id,
            schema_version=1,
            schema_hash=_hash_schema(frame),
            config_hash=config_hash,
            policy_hash=policy_hash,
            row_count=len(frame),
            part_files=[f"committed/{relative_path}"],
            checksum=checksum,
            created_at=_utcnow(),
            commit_marker="committed",
            manifest_uri=str(manifest_path.resolve()),
        )
        persisted_manifest = asdict(manifest)
        persisted_manifest.pop("manifest_uri")
        manifest_path.write_text(
            json.dumps(persisted_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest

    def _resolve_path(self, relative_path: str) -> Path:
        """将相对路径约束在根目录下，拒绝绝对路径和目录穿透。"""
        self._validate_relative_path(relative_path)
        root = self._root_dir.resolve()
        target = (self._root_dir / Path(relative_path)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("artifact relative_path must stay within manager root") from exc
        return target

    def _validate_relative_path(self, relative_path: str) -> None:
        """校验 artifact 相对路径不越界。"""
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError("artifact relative_path must not be absolute")
        if ".." in candidate.parts:
            raise ValueError("artifact relative_path must not contain parent traversal")

    def validate_manifest(self, manifest_path: Path) -> ArtifactManifest:
        """校验 manifest 文件存在并返回其内容。"""
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {manifest_path}")
        manifest = ArtifactManifest.from_path(manifest_path)
        if manifest.status != "committed":
            raise ValueError(f"artifact is not committed: {manifest.artifact_id}")
        artifact_path = Path(manifest.uri)
        if not artifact_path.exists():
            raise FileNotFoundError(f"artifact file missing: {artifact_path}")
        if _checksum_file(artifact_path) != manifest.checksum:
            raise ValueError(f"artifact checksum mismatch: {manifest.artifact_id}")
        return manifest


def _hash_schema(frame: pd.DataFrame) -> str:
    """根据 DataFrame schema 生成稳定 hash。"""
    schema_payload: dict[str, Any] = {
        "columns": [(column, str(dtype)) for column, dtype in frame.dtypes.items()]
    }
    return sha256(json.dumps(schema_payload, sort_keys=True).encode("utf-8")).hexdigest()


def _checksum_file(path: Path) -> str:
    """计算文件字节级 sha256 校验和。"""
    digest = sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cleanup_empty_parents(path: Path, stop_at: Path) -> None:
    """清理 tmp 目录下提交后留下的空目录。"""
    current = path
    stop = stop_at.resolve()
    while current.resolve() != stop:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _utcnow() -> str:
    """返回带 UTC 时区的 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()
