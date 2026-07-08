import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.border import ImageBorderComputer


def _item(image_id: str, image: Image.Image | None, error: str | None = None) -> ImageBatchItem:
    return ImageBatchItem(
        image_id=image_id,
        image_uri=f"/tmp/{image_id}.png",
        row={"image_id": image_id, "image_uri": f"/tmp/{image_id}.png"},
        data=b"image-bytes" if image is not None else None,
        image=image,
        error=error,
    )


def test_border_computer_detects_simple_white_padding(tmp_path) -> None:
    image = Image.new("RGB", (20, 20), color=(255, 255, 255))
    for x in range(5, 15):
        for y in range(5, 15):
            image.putpixel((x, y), (30, 80, 130))
    batch = ImageBatch(items=[_item("bordered", image)])

    result = ImageBorderComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bordered"]}),
            requested_parameters=frozenset(
                {"border_padding_ratio", "border_padding_sides", "border_padding_color"}
            ),
            config={},
            config_hash="border-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["border_padding_ratio"] >= 0.5
    assert row["border_padding_sides"] == "top,bottom,left,right"
    assert row["border_padding_color"] == "white"
    assert result.parameter_manifest["border_padding_ratio"]["computer"] == "image_border_computer"


def test_border_computer_reports_empty_values_without_border(tmp_path) -> None:
    image = Image.new("RGB", (20, 20), color=(20, 80, 140))
    batch = ImageBatch(items=[_item("plain", image)])

    result = ImageBorderComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["plain"]}),
            requested_parameters=frozenset(
                {"border_padding_ratio", "border_padding_sides", "border_padding_color"}
            ),
            config={},
            config_hash="border-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["border_padding_ratio"] == 0.0
    assert row["border_padding_sides"] == ""
    assert row["border_padding_color"] == "unknown"


def test_border_computer_writes_na_for_decode_errors(tmp_path) -> None:
    batch = ImageBatch(items=[_item("bad", None, "cannot decode")])

    result = ImageBorderComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"]}),
            requested_parameters=frozenset(
                {"border_padding_ratio", "border_padding_sides", "border_padding_color"}
            ),
            config={},
            config_hash="border-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert pd.isna(row["border_padding_ratio"])
    assert row["border_padding_sides"] == ""
    assert row["border_padding_color"] == "unknown"
