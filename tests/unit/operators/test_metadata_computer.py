import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.metadata import ImageFormatDetailComputer, ImageMetadataComputer


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


def test_format_detail_computer_detects_animated_images(tmp_path) -> None:
    image = Image.new("RGB", (8, 8), color=(100, 120, 140))
    image.is_animated = True
    image.n_frames = 3
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="animated",
                image_uri="/tmp/animated.gif",
                row={"image_id": "animated", "image_uri": "/tmp/animated.gif"},
                data=b"gif-bytes",
                image=image,
                error=None,
            )
        ]
    )

    result = ImageFormatDetailComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["animated"], "image_uri": ["/tmp/animated.gif"]}),
            requested_parameters=frozenset({"frame_count", "animated", "exif_orientation", "orientation_risk"}),
            config={},
            config_hash="format-detail-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["frame_count"] == 3
    assert row["animated"] is True
    assert pd.isna(row["exif_orientation"])
    assert row["orientation_risk"] is False
    assert result.parameter_manifest["animated"]["computer"] == "image_format_detail_computer"


def test_format_detail_computer_detects_orientation_risk(tmp_path) -> None:
    image = Image.new("RGB", (8, 12), color=(100, 120, 140))
    image.getexif()[274] = 6
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="rotated",
                image_uri="/tmp/rotated.jpg",
                row={"image_id": "rotated", "image_uri": "/tmp/rotated.jpg"},
                data=b"jpg-bytes",
                image=image,
                error=None,
            )
        ]
    )

    result = ImageFormatDetailComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["rotated"], "image_uri": ["/tmp/rotated.jpg"]}),
            requested_parameters=frozenset({"frame_count", "animated", "exif_orientation", "orientation_risk"}),
            config={},
            config_hash="format-detail-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["frame_count"] == 1
    assert row["animated"] is False
    assert row["exif_orientation"] == 6
    assert row["orientation_risk"] is True


def test_format_detail_computer_writes_safe_values_for_decode_errors(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="bad",
                image_uri="/tmp/bad.jpg",
                row={"image_id": "bad", "image_uri": "/tmp/bad.jpg"},
                data=None,
                image=None,
                error="cannot decode",
            )
        ]
    )

    result = ImageFormatDetailComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"], "image_uri": ["/tmp/bad.jpg"]}),
            requested_parameters=frozenset({"frame_count", "animated", "exif_orientation", "orientation_risk"}),
            config={},
            config_hash="format-detail-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert pd.isna(row["frame_count"])
    assert row["animated"] is False
    assert pd.isna(row["exif_orientation"])
    assert row["orientation_risk"] is False
