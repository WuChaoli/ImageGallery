from pathlib import Path

import pandas as pd
import pytest
from notebooks._helpers.cleaning_configs import (
    get_cleaning_v3_first_batch_operator_configs,
)
from notebooks._helpers.datasets import get_default_minio_sample_1000_raw_path
from notebooks._helpers.storage import load_minio_storage
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset
from image_gallery.storage.errors import StorageConnectionError

SAMPLE_DATASET_PATH = get_default_minio_sample_1000_raw_path()
FIRST_BATCH_OPERATORS = get_cleaning_v3_first_batch_operator_configs()


def _build_sample_1000_dataset() -> Dataset:
    return Dataset.from_path(str(SAMPLE_DATASET_PATH), storage=load_minio_storage())


def _write_image(path: Path, size: tuple[int, int] = (20, 20)) -> None:
    image = Image.new("RGB", size, color=(100, 120, 140))
    for x in range(size[0]):
        for y in range(size[1]):
            if (x + y) % 2 == 0:
                image.putpixel((x, y), (180, 60, 90))
    image.save(path)


def test_basic_cleaner_runs_first_batch_builtin_operators(tmp_path: Path) -> None:
    ok_path = tmp_path / "ok.png"
    duplicate_path = tmp_path / "duplicate.png"
    small_path = tmp_path / "small.png"
    blank_path = tmp_path / "blank.png"
    broken_path = tmp_path / "broken.jpg"
    _write_image(ok_path, size=(32, 32))
    duplicate_path.write_bytes(ok_path.read_bytes())
    _write_image(small_path, size=(4, 4))
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(blank_path)
    broken_path.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "dupe", "small", "blank", "bad"],
                "image_uri": [str(ok_path), str(duplicate_path), str(small_path), str(blank_path), str(broken_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner(
        [
            {"format.decode_check": {}},
            {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "drop"}},
            {"size.aspect_ratio_check": {}},
            {"size.megapixel_check": {"min_megapixels": 0.00001}},
            {"quality.blur_check": {"min_score": 0.0}},
            {"quality.brightness_check": {}},
            {"quality.contrast_check": {"min_score": 0.0}},
            {"content.blank_image_check": {}},
            {"duplicate.exact_duplicate_check": {}},
            {"duplicate.perceptual_duplicate_check": {}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    rows = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert rows.loc["ok", "final_action"] == "keep"
    assert rows.loc["bad", "decode_action"] == "drop"
    assert rows.loc["small", "dimension_action"] == "drop"
    assert rows.loc["blank", "blank_action"] == "drop"
    assert rows.loc["dupe", "exact_duplicate_action"] == "drop"
    assert rows.loc["dupe", "perceptual_duplicate_action"] == "drop"
    assert cleaner.preview().total_count == 5

    run_dir = next((tmp_path / "cleaning").iterdir())
    parameter_rows = pd.read_parquet(run_dir / "parameter_table.parquet")
    for column in [
        "aspect_ratio",
        "megapixels",
        "blur_score",
        "brightness_score",
        "contrast_score",
        "blank_score",
        "content_hash",
        "phash",
        "exact_duplicate_group_id",
        "exact_duplicate_count",
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
    ]:
        assert column in parameter_rows.columns
    assert (run_dir / "relations" / "duplicate_pairs.parquet").exists()
    assert (run_dir / "relations" / "perceptual_duplicate_pairs.parquet").exists()


def test_basic_cleaner_runs_first_batch_operators_on_sample_1000_raw_parquet(tmp_path: Path) -> None:
    assert SAMPLE_DATASET_PATH == get_default_minio_sample_1000_raw_path()

    if not SAMPLE_DATASET_PATH.exists():
        pytest.skip(f"sample raw dataset not found: {SAMPLE_DATASET_PATH}")

    try:
        dataset = _build_sample_1000_dataset()
    except (KeyError, StorageConnectionError) as exc:
        pytest.skip(f"skip sample_1000 integration test: {exc}")

    cleaner = BasicCleaner(FIRST_BATCH_OPERATORS)
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    preview = cleaner.preview()
    assert preview.total_count == 1000

    state = cleaner.state()
    assert list(state["operator_name"]) == [
        next(iter(item.keys())) for item in get_cleaning_v3_first_batch_operator_configs()
    ]

    run_dir = next((tmp_path / "cleaning").iterdir())
    parameter_table = pd.read_parquet(run_dir / "parameter_table.parquet")
    evaluation_table = pd.read_parquet(run_dir / "evaluation_table.parquet")
    expected_parameter_columns = [
        "width",
        "height",
        "aspect_ratio",
        "megapixels",
        "blur_score",
        "brightness_score",
        "contrast_score",
        "blank_score",
        "content_hash",
        "phash",
        "exact_duplicate_group_id",
        "exact_duplicate_count",
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
    ]
    for column in expected_parameter_columns:
        assert column in parameter_table.columns

    expected_evaluation_columns = [
        "decode_action",
        "decode_reason",
        "dimension_action",
        "dimension_reason",
        "aspect_ratio_action",
        "aspect_ratio_reason",
        "megapixel_action",
        "megapixel_reason",
        "blur_action",
        "blur_reason",
        "brightness_action",
        "brightness_reason",
        "contrast_action",
        "contrast_reason",
        "blank_action",
        "blank_reason",
        "exact_duplicate_action",
        "exact_duplicate_reason",
        "perceptual_duplicate_action",
        "perceptual_duplicate_reason",
        "final_action",
        "final_reason",
        "triggered_operator_names",
    ]
    for column in expected_evaluation_columns:
        assert column in evaluation_table.columns

    assert (run_dir / "relations" / "duplicate_pairs.parquet").exists()
    assert (run_dir / "relations" / "perceptual_duplicate_pairs.parquet").exists()


def test_basic_cleaner_runs_second_batch_light_quality_operators(tmp_path: Path) -> None:
    dark_path = tmp_path / "dark.png"
    border_path = tmp_path / "border.png"
    plain_path = tmp_path / "plain.png"
    Image.new("RGB", (24, 24), color=(0, 0, 0)).save(dark_path)
    border_image = Image.new("RGB", (24, 24), color=(255, 255, 255))
    for x in range(8, 16):
        for y in range(8, 16):
            border_image.putpixel((x, y), (30, 80, 130))
    border_image.save(border_path)
    Image.new("RGB", (24, 24), color=(90, 120, 150)).save(plain_path)
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["dark", "border", "plain"],
                "image_uri": [str(dark_path), str(border_path), str(plain_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner(
        [
            {"quality.exposure_check": {}},
            {"content.border_padding_check": {}},
            {"quality.noise_check": {"max_score": 0.01}},
            {"content.mono_color_check": {}},
            {"format.animated_image_check": {}},
            {"metadata.orientation_check": {}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    rows = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert rows.loc["dark", "exposure_action"] == "review"
    assert rows.loc["dark", "mono_color_action"] == "review"
    assert rows.loc["border", "border_padding_action"] == "review"
    assert rows.loc["plain", "animated_action"] == "keep"
    assert rows.loc["plain", "orientation_action"] == "keep"

    run_dir = next((tmp_path / "cleaning").iterdir())
    parameter_rows = pd.read_parquet(run_dir / "parameter_table.parquet")
    for column in [
        "dark_pixel_ratio",
        "bright_pixel_ratio",
        "clipped_pixel_ratio",
        "noise_score",
        "mono_color_score",
        "border_padding_ratio",
        "border_padding_sides",
        "border_padding_color",
        "frame_count",
        "animated",
        "exif_orientation",
        "orientation_risk",
    ]:
        assert column in parameter_rows.columns

    preview_path = cleaner.preview_html(
        str(tmp_path / "preview.html"),
        action="review",
        caption_columns=[
            "image_id",
            "final_action",
            "border_padding_ratio",
            "clipped_pixel_ratio",
            "noise_score",
            "mono_color_score",
        ],
    )
    assert preview_path.exists()
    assert "border_padding_ratio" in preview_path.read_text(encoding="utf-8")
