from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetExportResult, DatasetLoader, TabularDatasetExporter


class DemoLoader:
    """测试用 loader，验证 Dataset.load 可以委托外部资源加载。"""

    def __init__(self, dataset_path: str) -> None:
        self.dataset_path = dataset_path

    def load(self) -> Dataset:
        return Dataset.write(
            pd.DataFrame([{"image_id": "img-loader", "image_uri": "/tmp/loader.jpg"}]),
            self.dataset_path,
        )


def test_dataset_load_reads_existing_parquet(tmp_path: Path) -> None:
    output_path = str(tmp_path / "raw.parquet")
    pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}]).to_parquet(output_path, index=False)

    dataset = Dataset.load(output_path)

    assert dataset.dataset_path == output_path
    assert dataset.count() == 1


def test_dataset_load_delegates_loader(tmp_path: Path) -> None:
    loader: DatasetLoader = DemoLoader(str(tmp_path / "loaded.parquet"))

    dataset = Dataset.load(loader)

    assert dataset.to_frame().to_dict("records") == [{"image_id": "img-loader", "image_uri": "/tmp/loader.jpg"}]


def test_dataset_export_uses_tabular_exporter_and_drops_source_uri(tmp_path: Path) -> None:
    input_path = str(tmp_path / "raw.parquet")
    output_path = tmp_path / "export.csv"
    Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": "/managed/a.jpg",
                    "source_uri": "/external/a.jpg",
                    "width": 10,
                }
            ]
        ),
        input_path,
    )

    result = Dataset.load(input_path).export(TabularDatasetExporter(output_path))

    assert isinstance(result, DatasetExportResult)
    assert result.output_path == str(output_path)
    exported = Dataset.load(str(output_path))
    assert exported.to_frame().to_dict("records") == [{"image_id": "img-1", "image_uri": "/managed/a.jpg", "width": 10}]
