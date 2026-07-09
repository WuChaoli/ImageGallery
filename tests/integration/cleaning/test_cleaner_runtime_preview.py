from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _tiny_dataset(tmp_path: Path) -> Dataset:
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(first)
    Image.new("RGB", (2, 2), color=(0, 255, 0)).save(second)

    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": [str(first), str(second)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_result_preview_html_supports_operator_actions(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    result = BasicCleaner([{"format.decode_check": {}}]).run(dataset)

    output = result.preview_html(
        tmp_path / "decode_drop.html",
        operator_name="format.decode_check",
        actions="drop",
    )

    html = output.read_text(encoding="utf-8")
    assert "decode" in html
