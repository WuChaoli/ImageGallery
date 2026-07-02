from pathlib import Path

import pandas as pd

from image_gallery.importers import DatasetFileReader


def test_dataset_file_reader_reads_image_uri_column(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.parquet"
    pd.DataFrame(
        [
            {"image_uri": str(tmp_path / "a.jpg"), "source_uri": "original://a"},
            {"image_uri": str(tmp_path / "b.jpg"), "source_uri": "original://b"},
        ]
    ).to_parquet(dataset_path, index=False)

    records = list(DatasetFileReader(str(dataset_path)).read())

    assert [record.source_uri for record in records] == ["original://a", "original://b"]
    assert records[0].source_type == "dataset_file"
    assert records[0].local_path == Path(tmp_path / "a.jpg")


def test_dataset_file_reader_falls_back_to_image_uri_as_source_uri(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame([{"image_uri": str(tmp_path / "a.jpg")}]).to_csv(dataset_path, index=False)

    records = list(DatasetFileReader(str(dataset_path)).read())

    assert records[0].source_uri == str(tmp_path / "a.jpg")
