import hashlib

import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.hash import ImageHashComputer


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
