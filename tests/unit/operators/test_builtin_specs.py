import pandas as pd

from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_stage4_builtin_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "duplicate.exact_duplicate_check",
        "duplicate.near_duplicate_check",
        "format.decode_check",
        "quality.blur_check",
        "quality.brightness_check",
        "quality.contrast_check",
        "size.dimension_check",
    ]


def test_builtin_operator_specs_have_stage4_contract() -> None:
    registry = create_default_registry()

    decode_spec, _ = registry.resolve("format.decode_check")
    dimension_spec, _ = registry.resolve("size.dimension_check")
    blur_spec, _ = registry.resolve("quality.blur_check")
    duplicate_spec, _ = registry.resolve("duplicate.exact_duplicate_check")

    assert decode_spec.backend_name == "pillow_metadata_backend"
    assert decode_spec.parameter_columns == ["decode_ok", "decode_error"]
    assert decode_spec.evaluation_columns == ["decode_action", "decode_reason"]
    assert dimension_spec.parameter_columns == ["width", "height"]
    assert blur_spec.backend_name == "opencv_quality_backend"
    assert blur_spec.evaluation_columns == ["blur_score", "blur_action", "blur_reason"]
    assert duplicate_spec.backend_name == "image_hash_backend"
    assert duplicate_spec.evaluation_columns == [
        "exact_duplicate_group_id",
        "exact_duplicate_action",
        "exact_duplicate_reason",
    ]


def test_builtin_evaluators_return_declared_columns_without_mutating_parameters() -> None:
    registry = create_default_registry()
    parameter_table = pd.DataFrame(
        {
            "image_id": ["img-1", "img-2"],
            "decode_ok": [True, False],
            "decode_error": ["", "bad file"],
            "width": [100, 10],
            "height": [100, 10],
            "blur_score": [120.0, 10.0],
            "brightness_score": [128.0, 250.0],
            "contrast_score": [64.0, 2.0],
            "exact_duplicate_group_id": ["dup-1", ""],
        }
    )
    original = parameter_table.copy(deep=True)

    for operator_name in registry.list_operators():
        if operator_name == "duplicate.near_duplicate_check":
            continue
        spec, _ = registry.resolve(operator_name)
        result = spec.evaluate(parameter_table, spec.default_config)
        assert result.columns.tolist() == ["image_id", *spec.evaluation_columns]

    pd.testing.assert_frame_equal(parameter_table, original)
