from pathlib import Path

import pandas as pd

from image_gallery.operators.computers.base import (
    ComputerCapability,
    ComputerRuntimePolicy,
    ExecutionMode,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    execution_mode = ExecutionMode.PER_IMAGE
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
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def test_parameter_computer_contract_has_default_runtime_and_capability() -> None:
    computer = DemoComputer()
    assert computer.runtime_policy == ComputerRuntimePolicy()
    assert computer.capability == ComputerCapability()


def test_parameter_computer_contract_defaults_support_expected_checkpoint_modes() -> None:
    class AggregateComputer(ParameterComputer):
        name = "aggregate_computer"
        execution_mode = ExecutionMode.DATASET_AGGREGATE
        produced_parameters = frozenset({"demo_group"})

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(
                parameter_updates=pd.DataFrame(
                    {
                        "image_id": request.parameter_table["image_id"],
                        "demo_group": ["g1"] * len(request.parameter_table),
                    }
                ),
                relation_updates={},
                artifact_refs={},
                parameter_manifest={},
            )

    assert "batch" in DemoComputer().capability.checkpoint_strategies
    assert (
        "whole_node" in AggregateComputer().capability.checkpoint_strategies
        or "stage" in AggregateComputer().capability.checkpoint_strategies
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
