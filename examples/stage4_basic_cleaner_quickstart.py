from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def main() -> None:
    """运行阶段 4 BasicCleaner 最小示例。"""
    with TemporaryDirectory(prefix="image_gallery_stage4_") as workspace:
        root = Path(workspace)
        first = root / "first.png"
        duplicate = root / "duplicate.png"
        unique = root / "unique.png"
        Image.new("RGB", (24, 24), color=(20, 40, 60)).save(first)
        duplicate.write_bytes(first.read_bytes())
        Image.new("RGB", (24, 24), color=(200, 210, 220)).save(unique)

        raw_dataset = Dataset.write(
            pd.DataFrame(
                {
                    "image_id": ["img-1", "img-2", "img-3"],
                    "image_uri": [str(first), str(duplicate), str(unique)],
                }
            ),
            str(root / "raw.parquet"),
        )
        cleaner = BasicCleaner(
            [
                {"format.decode_check": {}},
                {"size.dimension_check": {"min_width": 10, "min_height": 10}},
                {"duplicate.exact_duplicate_check": {"action": "drop"}},
            ]
        )
        result = cleaner.run(raw_dataset, output_dir=root / "cleaning")
        preview = result.preview()
        full = result.export("full", str(root / "full.parquet"))
        clean = result.export("clean", str(root / "clean.parquet"))
        dropped = result.export("dropped", str(root / "dropped.parquet"))
        parameter_table = result.export_table("parameter", root / "parameter_table.parquet")
        evaluation_table = result.export_table("evaluation", root / "evaluation_table.parquet")

        print(f"run_id={result.run_id}")
        print(f"parameter_table={parameter_table}")
        print(f"evaluation_table={evaluation_table}")
        print(
            "preview="
            f"clean:{preview.clean_count},review:{preview.review_count},"
            f"dropped:{preview.dropped_count},restricted:{preview.restricted_count}"
        )
        print(f"exports=full:{full.count()},clean:{clean.count()},dropped:{dropped.count()}")


if __name__ == "__main__":
    main()
