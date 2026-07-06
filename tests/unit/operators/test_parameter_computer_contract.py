from pathlib import Path

import pandas as pd

from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is not None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "demo_score": [1.0 for _ in request.image_batch.items],
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "demo_score": {
                    "computer": self.name,
                    "stage": self.stage.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def test_parameter_computer_contract_uses_shared_image_batch(tmp_path: Path) -> None:
    image_batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-1",
                image_uri="/tmp/img-1.png",
                row={"image_id": "img-1", "image_uri": "/tmp/img-1.png"},
                data=b"fake",
                image=None,
                error=None,
            )
        ]
    )
    request = ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/img-1.png"]}),
        requested_parameters=frozenset({"demo_score"}),
        config={},
        config_hash="abc123",
        artifacts_dir=tmp_path,
        image_batch=image_batch,
    )

    result = DemoComputer().compute(request)

    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "img-1", "demo_score": 1.0}
    ]
    assert result.parameter_manifest["demo_score"]["computer"] == "demo_computer"
