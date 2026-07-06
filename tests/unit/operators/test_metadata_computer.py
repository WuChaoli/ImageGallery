import pandas as pd

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.metadata import ImageMetadataComputer


def test_metadata_computer_uses_shared_decoded_batch(tmp_path) -> None:
    class FakeImage:
        width = 8
        height = 6
        format = "PNG"

    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-1",
                image_uri="/tmp/ok.png",
                row={"image_id": "img-1", "image_uri": "/tmp/ok.png"},
                data=b"abc",
                image=FakeImage(),
                error=None,
            )
        ]
    )
    result = ImageMetadataComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/ok.png"]}),
            requested_parameters=frozenset({"decode_ok", "decode_error", "width", "height", "file_size"}),
            config={},
            config_hash="metadata-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [
        {
            "image_id": "img-1",
            "decode_error": "",
            "decode_ok": True,
            "file_size": 3,
            "height": 6,
            "width": 8,
        }
    ]


def test_metadata_computer_records_shared_decode_error(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-bad",
                image_uri="/tmp/bad.png",
                row={"image_id": "img-bad", "image_uri": "/tmp/bad.png"},
                data=None,
                image=None,
                error="cannot identify image file",
            )
        ]
    )
    result = ImageMetadataComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-bad"], "image_uri": ["/tmp/bad.png"]}),
            requested_parameters=frozenset({"decode_ok", "decode_error", "width", "height"}),
            config={},
            config_hash="metadata-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["image_id"] == "img-bad"
    assert row["decode_ok"] is False
    assert row["decode_error"] == "cannot identify image file"
    assert pd.isna(row["width"])
    assert pd.isna(row["height"])
