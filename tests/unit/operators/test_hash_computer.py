import hashlib
import re

import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.hash import ImageHashComputer, ImagePerceptualHashComputer


def test_hash_computer_uses_raw_bytes_for_content_hash(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-1",
                image_uri="/tmp/img-1.png",
                row={"image_id": "img-1"},
                data=b"same-bytes",
                image=Image.new("RGB", (1, 1)),
                error=None,
            )
        ]
    )

    result = ImageHashComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-1"]}),
            requested_parameters=frozenset({"content_hash"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "img-1", "content_hash": hashlib.sha256(b"same-bytes").hexdigest()}
    ]


def test_perceptual_hash_computer_returns_stable_16_char_hex(tmp_path) -> None:
    image = Image.new("RGB", (32, 32), color=(120, 130, 140))
    batch = ImageBatch(
        items=[
            ImageBatchItem("img-1", "/tmp/img-1.png", {"image_id": "img-1"}, b"bytes-1", image, None),
            ImageBatchItem("img-2", "/tmp/img-2.png", {"image_id": "img-2"}, b"bytes-2", image.copy(), None),
        ]
    )

    result = ImagePerceptualHashComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-1", "img-2"]}),
            requested_parameters=frozenset({"phash"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    values = result.parameter_updates["phash"].tolist()
    assert values[0] == values[1]
    assert re.fullmatch(r"[0-9a-f]{16}", values[0])
    assert result.parameter_manifest["phash"]["computer"] == "image_perceptual_hash_computer"
    assert result.parameter_manifest["phash"]["execution_mode"] == "per_image"


def test_perceptual_hash_computer_returns_empty_hash_for_unreadable_image(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem("bad", "/tmp/bad.jpg", {"image_id": "bad"}, None, None, "cannot decode"),
        ]
    )

    result = ImagePerceptualHashComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"]}),
            requested_parameters=frozenset({"phash"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [{"image_id": "bad", "phash": ""}]
