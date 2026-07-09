from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.runtime import CleaningRuntime, RunOptions
from image_gallery.dataset import Dataset


def _write_tiny_image(path: Path, color: tuple[int, int, int]) -> None:
    """写入最小 PNG 以便构造 dataset fixture。"""
    with Image.new("RGB", (2, 2), color=color) as image:
        image.save(path, format="PNG")


@pytest.fixture
def tiny_dataset(tmp_path: Path) -> Dataset:
    """生成一个两行的 Parquet 数据集，供 runtime 测试读取。"""
    first_path = tmp_path / "one.png"
    second_path = tmp_path / "two.png"
    _write_tiny_image(first_path, (255, 0, 0))
    _write_tiny_image(second_path, (0, 255, 0))

    frame = pd.DataFrame(
        {
            "image_id": ["img-1", "img-2"],
            "image_uri": [str(first_path), str(second_path)],
        }
    )
    dataset_path = tmp_path / "raw.parquet"
    frame.to_parquet(dataset_path, index=False)
    return Dataset.from_path(str(dataset_path))


def test_runtime_retries_stage_once_then_completes(tmp_path: Path, tiny_dataset: Dataset) -> None:
    runtime = CleaningRuntime(cache_root=tmp_path)
    options = RunOptions(run_id="run-1", retry_max_attempts=2)

    result = runtime.run_fake_stage_for_test(
        dataset=tiny_dataset,
        options=options,
        fail_first_attempt=True,
    )

    assert result.status == "completed"
    assert result.attempt_count == 2
    assert runtime.state_store is not None
    assert runtime.state_store.list_events("run-1")[-1].event_type == "run_completed"


def test_runtime_retries_stage_once_but_fails_when_no_retry_budget(tmp_path: Path, tiny_dataset: Dataset) -> None:
    runtime = CleaningRuntime(cache_root=tmp_path)
    options = RunOptions(run_id="run-3", retry_max_attempts=1)

    result = runtime.run_fake_stage_for_test(
        dataset=tiny_dataset,
        options=options,
        fail_first_attempt=True,
    )

    assert result.status == "failed"
    assert result.attempt_count == 1
    assert runtime.state_store is not None
    assert runtime.state_store.list_events("run-3")[-1].event_type == "run_failed"
    assert runtime.state_store.load_run("run-3").status == "failed"


def test_runtime_run_graph_completes_via_fake_stage(tmp_path: Path, tiny_dataset: Dataset) -> None:
    runtime = CleaningRuntime(cache_root=tmp_path)
    graph = CleaningStateGraph(nodes=tuple(), plan_hash="test-graph")

    result = runtime.run_graph(
        graph=graph,
        dataset=tiny_dataset,
        run_options=RunOptions(run_id="run-2"),
    )

    assert result.status == "completed"
