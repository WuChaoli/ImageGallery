import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.quality import ImageQualityComputer, ImageQualityDetailComputer


def _item(image_id: str, image: Image.Image | None, error: str | None = None) -> ImageBatchItem:
    return ImageBatchItem(
        image_id=image_id,
        image_uri=f"/tmp/{image_id}.png",
        row={"image_id": image_id, "image_uri": f"/tmp/{image_id}.png"},
        data=b"image-bytes" if image is not None else None,
        image=image,
        error=error,
    )


def test_quality_computer_produces_requested_scores(tmp_path) -> None:
    image = Image.new("L", (4, 4), color=128)
    batch = ImageBatch(items=[_item("solid", image)])

    result = ImageQualityComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["solid"]}),
            requested_parameters=frozenset({"blur_score", "brightness_score", "contrast_score", "blank_score"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["image_id"] == "solid"
    assert row["brightness_score"] == 128.0
    assert row["contrast_score"] == 0.0
    assert row["blank_score"] == 1.0
    assert row["blur_score"] == 0.0


def test_quality_computer_writes_na_for_decode_errors(tmp_path) -> None:
    batch = ImageBatch(items=[_item("bad", None, "cannot decode")])

    result = ImageQualityComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"]}),
            requested_parameters=frozenset({"blur_score", "brightness_score", "contrast_score", "blank_score"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert pd.isna(row["blur_score"])
    assert pd.isna(row["brightness_score"])
    assert pd.isna(row["contrast_score"])
    assert pd.isna(row["blank_score"])


def test_quality_detail_computer_produces_exposure_noise_and_mono_scores(tmp_path) -> None:
    dark = Image.new("RGB", (8, 8), color=(0, 0, 0))
    bright = Image.new("RGB", (8, 8), color=(255, 255, 255))
    checker = Image.new("RGB", (8, 8), color=(0, 0, 0))
    for x in range(8):
        for y in range(8):
            if (x + y) % 2 == 0:
                checker.putpixel((x, y), (255, 255, 255))
    batch = ImageBatch(items=[_item("dark", dark), _item("bright", bright), _item("checker", checker)])

    result = ImageQualityDetailComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["dark", "bright", "checker"]}),
            requested_parameters=frozenset(
                {
                    "dark_pixel_ratio",
                    "bright_pixel_ratio",
                    "clipped_pixel_ratio",
                    "noise_score",
                    "mono_color_score",
                }
            ),
            config={},
            config_hash="quality-detail-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    rows = result.parameter_updates.set_index("image_id")
    assert rows.loc["dark", "dark_pixel_ratio"] == 1.0
    assert rows.loc["bright", "bright_pixel_ratio"] == 1.0
    assert rows.loc["dark", "clipped_pixel_ratio"] == 1.0
    assert rows.loc["checker", "noise_score"] > rows.loc["dark", "noise_score"]
    assert rows.loc["dark", "mono_color_score"] == 1.0
    assert rows.loc["checker", "mono_color_score"] < 1.0
    assert result.parameter_manifest["noise_score"]["computer"] == "image_quality_detail_computer"
    assert result.parameter_manifest["noise_score"]["execution_mode"] == "per_image"


def test_quality_detail_computer_writes_na_for_decode_errors(tmp_path) -> None:
    batch = ImageBatch(items=[_item("bad", None, "cannot decode")])

    result = ImageQualityDetailComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"]}),
            requested_parameters=frozenset(
                {
                    "dark_pixel_ratio",
                    "bright_pixel_ratio",
                    "clipped_pixel_ratio",
                    "noise_score",
                    "mono_color_score",
                }
            ),
            config={},
            config_hash="quality-detail-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert pd.isna(row["dark_pixel_ratio"])
    assert pd.isna(row["bright_pixel_ratio"])
    assert pd.isna(row["clipped_pixel_ratio"])
    assert pd.isna(row["noise_score"])
    assert pd.isna(row["mono_color_score"])
