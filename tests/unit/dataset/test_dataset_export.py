from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset


def test_dataset_export_keeps_image_uri_and_drops_source_uri(tmp_path: Path) -> None:
    input_uri = str(tmp_path / "raw.parquet")
    output_uri = str(tmp_path / "export.csv")
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
        input_uri,
    )

    exported = Dataset.from_uri(input_uri).export(output_uri, address_policy="keep")

    frame = exported.to_frame()
    assert frame.to_dict("records") == [{"image_id": "img-1", "image_uri": "/managed/a.jpg", "width": 10}]
