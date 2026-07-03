from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.errors import BackendExecutionError
from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendOperatorRequest
from image_gallery.operators.backends.fastdup_backend import FastdupSimilarityBackend, build_fastdup_input


def test_fastdup_backend_reports_missing_dependency(tmp_path: Path) -> None:
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(tmp_path / "a.png")]}),
        str(tmp_path / "raw.parquet"),
    )

    with pytest.raises(BackendExecutionError, match="install image_gallery\\[fastdup\\]"):
        FastdupSimilarityBackend().compute_parameters(
            dataset,
            dataset.to_frame(),
            [BackendOperatorRequest("duplicate.near_duplicate_check", ["near_duplicate_group_id"], {}, "a")],
            tmp_path / "artifacts",
        )


def test_build_fastdup_input_writes_image_list(tmp_path: Path) -> None:
    parameter_table = pd.DataFrame({"image_uri": ["/tmp/a.png", "/tmp/b.png"]})

    input_path = build_fastdup_input(parameter_table, tmp_path)

    assert input_path.read_text(encoding="utf-8").splitlines() == ["/tmp/a.png", "/tmp/b.png"]
