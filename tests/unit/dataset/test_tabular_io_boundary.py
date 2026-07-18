from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset._tabular_io import format_from_path, read_frame, write_frame


@pytest.mark.parametrize(
    ("suffix", "expected_format"),
    [(".parquet", "parquet"), (".CSV", "csv"), (".json", "jsonl"), (".jsonl", "jsonl")],
)
def test_private_tabular_io_preserves_format_dispatch(suffix: str, expected_format: str) -> None:
    assert format_from_path(f"dataset{suffix}") == expected_format


@pytest.mark.parametrize("file_format", ["parquet", "csv", "jsonl"])
def test_private_tabular_io_round_trips_supported_formats(tmp_path: Path, file_format: str) -> None:
    suffix = ".jsonl" if file_format == "jsonl" else f".{file_format}"
    output_path = tmp_path / f"raw{suffix}"
    frame = pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}])

    write_frame(frame, output_path, file_format)

    assert read_frame(str(output_path), file_format).to_dict("records") == frame.to_dict("records")
