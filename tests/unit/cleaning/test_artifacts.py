import json
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.artifacts import ArtifactManager


def test_artifact_manager_commits_dataframe_with_manifest(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)
    frame = pd.DataFrame({"image_id": ["img-1"], "score": [1.0]})

    manifest = manager.commit_dataframe_artifact(
        artifact_id="artifact-1",
        artifact_type="parameter_part",
        owner_node_id="parameter.demo",
        frame=frame,
        relative_path="tables/parameter_part.parquet",
        config_hash="config",
        policy_hash="policy",
    )

    assert (tmp_path / "committed" / "tables" / "parameter_part.parquet").exists()
    assert Path(manifest.manifest_uri).exists()
    assert manifest.row_count == 1
    assert manifest.commit_marker == "committed"
    manifest_payload = json.loads(
        (tmp_path / "committed" / "tables" / "parameter_part.parquet.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_payload["artifact_id"] == "artifact-1"
    assert manifest_payload["status"] == "committed"
    assert "manifest_uri" not in manifest_payload


def test_artifact_manager_commits_dataframe_through_tmp_and_committed_dirs(tmp_path: Path) -> None:
    """DataFrame artifact 应先写临时区，再提交到 committed 区并记录 status/uri。"""
    manager = ArtifactManager(tmp_path)
    frame = pd.DataFrame({"image_id": ["img-1"], "score": [1.0]})

    manifest = manager.commit_dataframe_artifact(
        artifact_id="artifact-1",
        artifact_type="parameter_part",
        owner_node_id="parameter.demo",
        frame=frame,
        relative_path="tables/parameter_part.parquet",
        config_hash="config",
        policy_hash="policy",
    )

    assert manifest.status == "committed"
    assert "committed" in Path(manifest.uri).parts
    assert Path(manifest.uri).exists()
    assert not (tmp_path / "tmp" / "tables" / "parameter_part.parquet").exists()


def test_artifact_manager_rejects_missing_manifest(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.validate_manifest(tmp_path / "missing.json")


def test_artifact_manager_rejects_directory_traversal(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)
    frame = pd.DataFrame({"image_id": ["img-1"], "score": [1.0]})

    with pytest.raises(ValueError, match="must not contain parent traversal"):
        manager.commit_dataframe_artifact(
            artifact_id="artifact-2",
            artifact_type="parameter_part",
            owner_node_id="parameter.demo",
            frame=frame,
            relative_path="../outside.parquet",
            config_hash="config",
            policy_hash="policy",
        )

    assert not (tmp_path / "outside.parquet").exists()


def test_artifact_manager_rejects_absolute_path(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)
    frame = pd.DataFrame({"image_id": ["img-1"], "score": [1.0]})
    outside = tmp_path.parent / "outside.artifact.parquet"

    with pytest.raises(ValueError, match="must not be absolute"):
        manager.commit_dataframe_artifact(
            artifact_id="artifact-3",
            artifact_type="parameter_part",
            owner_node_id="parameter.demo",
            frame=frame,
            relative_path=str(outside),
            config_hash="config",
            policy_hash="policy",
        )

    assert not outside.exists()
