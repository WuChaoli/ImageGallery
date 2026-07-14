from pathlib import Path

import pandas as pd

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.execution import CleanerExecution
from image_gallery.dataset import Dataset


def test_basic_cleaner_compile_returns_execution() -> None:
    execution = BasicCleaner([{"decode": {}}]).compile()

    assert isinstance(execution, CleanerExecution)
    assert "evaluation.decode" in execution.plan()["node_id"].tolist()


def test_dry_run_reports_selected_operator() -> None:
    execution = BasicCleaner([{"decode": {}}]).compile()

    dry_run = execution.dry_run(dataset=None)

    assert "decode" in dry_run.selected_operators
    assert dry_run.errors == []


def test_dry_run_reports_missing_dataset_columns(tmp_path: Path) -> None:
    dataset = Dataset.write(pd.DataFrame({"image_id": ["img-1"]}), str(tmp_path / "missing-uri.parquet"))

    dry_run = BasicCleaner([{"decode": {}}]).compile().dry_run(dataset)

    assert dry_run.errors == ["dataset.image_uri column is required"]


def test_run_persists_label_tags_and_stable_sample(tmp_path: Path) -> None:
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": ["missing-1.jpg", "missing-2.jpg", "missing-3.jpg"],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    execution = BasicCleaner([{"decode": {}}]).compile()

    result = execution.run(dataset, label="sample-smoke", tags=["sample", "unit"], sample=2)

    assert len(result.result("decode")) == 2
    record = execution.runtime.state_store.load_run(result.run_id)  # type: ignore[union-attr]
    assert record.label == "sample-smoke"
    assert record.tags == ["sample", "unit"]
    assert record.sample_size == 2
    assert record.sample_rule is not None
    assert isinstance(record.sample_rule["random_state"], int)
