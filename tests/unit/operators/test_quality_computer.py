import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.quality import ImageQualityComputer


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
