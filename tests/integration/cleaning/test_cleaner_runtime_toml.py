from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _tiny_dataset(tmp_path: Path) -> Dataset:
    image_path = tmp_path / "tiny.png"
    Image.new("RGB", (24, 24), color=(120, 140, 160)).save(image_path)
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["tiny"],
                "image_uri": [str(image_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_from_toml_run_matches_python_api(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[cleaner]
operators = ["QUALITY"]

[[operator]]
name = "quality.blur_check"
min_score = 0.0
action = "review"
""".strip(),
        encoding="utf-8",
    )

    toml_result = BasicCleaner.from_toml(config_path).run(dataset)
    python_result = BasicCleaner(
        ["QUALITY"],
        operator_config_overrides={
            "quality.blur_check": {
                "min_score": 0.0,
                "action": "review",
            }
        },
    ).run(dataset)

    toml_evaluation_path = toml_result.export_table("evaluation", tmp_path / "toml_evaluation.parquet")
    python_evaluation_path = python_result.export_table("evaluation", tmp_path / "python_evaluation.parquet")

    assert toml_result.status() == "completed"
    assert python_result.status() == "completed"
    assert pd.read_parquet(toml_evaluation_path).equals(pd.read_parquet(python_evaluation_path))


def test_export_config_template_writes_selector_and_override_sections(tmp_path: Path) -> None:
    template_path = BasicCleaner.export_config_template(
        tmp_path / "cleaning_runtime.toml",
        operators=["QUALITY", "DUPLICATE"],
    )

    content = template_path.read_text(encoding="utf-8")

    assert template_path == tmp_path / "cleaning_runtime.toml"
    assert '[cleaner]\noperators = ["QUALITY", "DUPLICATE"]' in content
    assert '[[operator]]\nname = "quality.blur_check"' in content
    assert '[[operator]]\nname = "duplicate.exact_duplicate_check"' in content
