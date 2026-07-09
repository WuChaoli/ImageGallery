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

    assert (tmp_path / "tables" / "parameter_part.parquet").exists()
    assert Path(manifest.manifest_uri).exists()
    assert manifest.row_count == 1
    assert manifest.commit_marker == "committed"


def test_artifact_manager_rejects_missing_manifest(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.validate_manifest(tmp_path / "missing.json")
