from pathlib import Path

import pandas as pd

from image_gallery.cleaning import BasicCleaner, CleanerExecution, CleanerResult
from image_gallery.dataset import Dataset


def _dataset(tmp_path: Path) -> Dataset:
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": ["platform://local/a.jpg", "platform://local/b.jpg"],
                "source_uri": ["file:///a.jpg", "file:///b.jpg"],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_basic_cleaner_compile_returns_execution() -> None:
    cleaner = BasicCleaner([{"format.decode_check": {}}])

    execution = cleaner.compile()

    assert isinstance(execution, CleanerExecution)


def test_basic_cleaner_plan_auto_compiles_without_running_dataset(tmp_path: Path) -> None:
    cleaner = BasicCleaner([{"format.decode_check": {}}])

    frame = cleaner.plan()

    assert "evaluation.format.decode_check" in frame["node_id"].tolist()


def test_basic_cleaner_run_returns_result_and_hides_process_outputs(tmp_path: Path) -> None:
    result = BasicCleaner([{"format.decode_check": {}}]).run(_dataset(tmp_path), label="unit")

    assert isinstance(result, CleanerResult)
    assert result.status() in {"completed", "running"}
    assert not (tmp_path / "parameter_table.parquet").exists()
