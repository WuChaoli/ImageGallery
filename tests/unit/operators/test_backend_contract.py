import pandas as pd

from image_gallery.operators.backends.base import BackendOperatorRequest, BackendResult


def test_backend_request_and_result_hold_parameter_contract() -> None:
    request = BackendOperatorRequest(
        operator_name="quality.demo_check",
        parameter_columns=["demo_score"],
        config={"action": "review"},
        config_hash="abc",
    )
    result = BackendResult(
        parameter_updates=pd.DataFrame({"image_id": ["img-1"], "demo_score": [1.0]}),
        relation_updates={},
        artifact_refs={},
    )

    assert request.operator_name == "quality.demo_check"
    assert "image_id" in result.parameter_updates.columns
