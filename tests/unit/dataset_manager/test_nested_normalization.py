import json
from typing import cast

import numpy as np
import pandas as pd
import pytest

from image_gallery.dataset_manager import (
    ColumnSpec,
    ListFieldType,
    StructField,
    StructFieldType,
    ValidationError,
)
from image_gallery.dataset_manager._physical_schema import canonicalize_value


def nested_type() -> ListFieldType:
    return ListFieldType(
        StructFieldType(
            (
                StructField("label", "string", required=True),
                StructField("score", "double"),
                StructField("rank", "integer"),
            )
        ),
        element_required=True,
    )


def test_canonical_nested_values_are_json_safe_and_follow_schema_order() -> None:
    value = [{"rank": np.int32(7), "label": "cat"}]

    normalized = canonicalize_value(nested_type(), value, required=False, path="annotations")
    normalized_rows = cast(list[dict[str, object]], normalized)

    assert normalized == [{"label": "cat", "score": None, "rank": 7}]
    assert list(normalized_rows[0]) == ["label", "score", "rank"]
    assert json.loads(json.dumps(normalized)) == normalized


def test_canonical_values_keep_null_and_empty_list_distinct() -> None:
    assert canonicalize_value(nested_type(), None, required=False, path="annotations") is None
    assert canonicalize_value(nested_type(), [], required=False, path="annotations") == []
    assert canonicalize_value("double", pd.NA, required=False, path="score") is None
    assert canonicalize_value("double", np.float64("nan"), required=False, path="score") is None


@pytest.mark.parametrize(
    ("field_type", "value"),
    [
        (nested_type(), [{"score": 0.9}]),
        (nested_type(), [{"label": "cat", "unknown": 1}]),
        (nested_type(), [None]),
        (nested_type(), ({"label": "cat"},)),
        ("integer", True),
        ("integer", 2**31),
        ("long", -(2**63) - 1),
        ("string", 1),
        ("double", float("inf")),
        ("double", float("-inf")),
    ],
)
def test_canonical_values_reject_invalid_nested_and_scalar_values(field_type, value) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    with pytest.raises(ValidationError):
        canonicalize_value(field_type, value, required=False, path="value")


def test_required_null_is_rejected_after_missing_value_normalization() -> None:
    for value in (None, pd.NA, np.float64("nan")):
        with pytest.raises(ValidationError, match="required"):
            canonicalize_value("double", value, required=True, path="score")


def test_column_spec_is_accepted_as_canonicalization_contract() -> None:
    column = ColumnSpec("annotations", nested_type())

    assert canonicalize_value(column.field_type, [], required=column.required, path=column.name) == []
