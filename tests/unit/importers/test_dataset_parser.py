from pathlib import Path

import pandas as pd
import pytest

from image_gallery.importers import DatasetParser


def test_dataset_parser_reads_default_image_uri_column(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.parquet"
    pd.DataFrame(
        [
            {"image_uri": str(tmp_path / "a.jpg"), "source_uri": "original://a"},
            {"image_uri": str(tmp_path / "b.jpg"), "source_uri": "original://b"},
        ]
    ).to_parquet(dataset_path, index=False)

    records = DatasetParser(dataset_path).parse()

    assert [record.source_uri for record in records] == ["original://a", "original://b"]
    assert records[0].source_type == "dataset"
    assert records[0].local_path == Path(tmp_path / "a.jpg")


def test_dataset_parser_accepts_custom_image_uri_column(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame(
        [
            {"path": str(tmp_path / "a.jpg"), "origin": "original://a"},
            {"path": str(tmp_path / "b.jpg"), "origin": ""},
        ]
    ).to_csv(dataset_path, index=False)

    records = DatasetParser(dataset_path, image_uri_column="path", source_uri_column="origin").parse()

    assert [record.source_uri for record in records] == ["original://a", str(tmp_path / "b.jpg")]
    assert records[0].source_file_name == "a.jpg"
    assert records[0].source_relative_path == "a.jpg"


def test_dataset_parser_falls_back_to_image_uri_when_source_uri_column_is_missing(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame([{"image_uri": str(tmp_path / "a.jpg")}]).to_csv(dataset_path, index=False)

    records = DatasetParser(dataset_path).parse()

    assert records[0].source_uri == str(tmp_path / "a.jpg")


def test_dataset_parser_rejects_missing_image_uri_column(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame([{"path": str(tmp_path / "a.jpg")}]).to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="missing image uri column"):
        DatasetParser(dataset_path).parse()


def test_dataset_parser_rejects_empty_column_names(tmp_path: Path) -> None:
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame([{"image_uri": str(tmp_path / "a.jpg")}]).to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="image_uri_column must not be empty"):
        DatasetParser(dataset_path, image_uri_column="").parse()
    with pytest.raises(ValueError, match="source_uri_column must not be empty"):
        DatasetParser(dataset_path, source_uri_column="").parse()
