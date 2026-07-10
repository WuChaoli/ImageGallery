from pathlib import Path

import pandas as pd

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.context import build_run_paths, create_run_context
from image_gallery.dataset import Dataset


def test_build_run_paths_uses_stage3_output_contract(tmp_path: Path) -> None:
    paths = build_run_paths(tmp_path / "run-1")

    assert paths.run_dir == tmp_path / "run-1"
    assert paths.parameter_table_path == tmp_path / "run-1" / "tables" / "parameter_table.parquet"
    assert paths.evaluation_table_path == tmp_path / "run-1" / "tables" / "evaluation_table.parquet"
    assert paths.operator_outputs_path == tmp_path / "run-1" / "manifests" / "operator_outputs.json"
    assert paths.parameter_manifest_path == tmp_path / "run-1" / "manifests" / "parameter_manifest.json"
    assert paths.relations_dir == tmp_path / "run-1" / "relations"
    assert paths.artifacts_dir == tmp_path / "run-1" / "artifacts"
    assert paths.manifests_dir == tmp_path / "run-1" / "manifests"
    assert paths.state_path == tmp_path / "run-1" / "state.json"


def test_create_run_context_generates_unique_run_dirs(tmp_path: Path) -> None:
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": ["platform://local/a.jpg"]}),
        str(tmp_path / "raw.parquet"),
    )
    operator_configs = parse_operator_configs([{"quality.demo_check": {"action": "review"}}])

    first = create_run_context(dataset, "basic", operator_configs, tmp_path / "cleaning_outputs")
    second = create_run_context(dataset, "basic", operator_configs, tmp_path / "cleaning_outputs")

    assert first.run_id != second.run_id
    assert first.dataset_fingerprint == dataset.fingerprint()
    assert first.cleaner_type == "basic"
    assert first.operator_configs == operator_configs
    assert first.paths.run_dir.parent == tmp_path / "cleaning_outputs"
    assert second.paths.run_dir.parent == tmp_path / "cleaning_outputs"
