"""Artifact 持久化与 manifest 管理。"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
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
    def from_path(cls, path: Path) -> "ArtifactManifest":
        """从 manifest 文件反序列化。"""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            artifact_id=str(payload["artifact_id"]),
            artifact_type=str(payload["artifact_type"]),
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
            manifest_uri=str(path),
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
        target = self._root_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(target, index=False)
        checksum = _checksum_file(target)
        manifest_path = target.with_name(f"{target.name}.manifest.json")
        manifest = ArtifactManifest(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            owner_node_id=owner_node_id,
            schema_version=1,
            schema_hash=_hash_schema(frame),
            config_hash=config_hash,
            policy_hash=policy_hash,
            row_count=len(frame),
            part_files=[relative_path],
            checksum=checksum,
            created_at=_utcnow(),
            commit_marker="committed",
            manifest_uri=str(manifest_path.resolve()),
        )
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest

    def validate_manifest(self, manifest_path: Path) -> ArtifactManifest:
        """校验 manifest 文件存在并返回其内容。"""
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {manifest_path}")
        return ArtifactManifest.from_path(manifest_path)


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


def _utcnow() -> str:
    """返回带 UTC 时区的 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()
