from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner


def _tiny_dataset(tmp_path: Path):
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(first)
    Image.new("RGB", (2, 2), color=(0, 255, 0)).save(second)

    return pd.DataFrame(
        {
            "image_id": ["img-1", "img-2"],
            "image_uri": [str(first), str(second)],
        }
    )


def test_result_preview_html_supports_operator_actions(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    import pandas as pd

    raw_dataset = pd.read_parquet
    _ = raw_dataset
    dataset = None
    dataset = BasicCleaner([{"format.decode_check": {}}]).run(
        __import__("image_gallery.dataset", fromlist=["Dataset"]).Dataset.write(
            pd.DataFrame(_tiny_dataset(tmp_path)),
            str(tmp_path / "raw.parquet"),
        )
    )

    output = dataset.preview_html(
        tmp_path / "decode_drop.html",
        operator_name="format.decode_check",
        actions="drop",
    )

    html = output.read_text(encoding="utf-8")
    assert "decode" in html
