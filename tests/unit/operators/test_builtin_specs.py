import pandas as pd

from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_only_first_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "content.blank_image_check",
        "duplicate.exact_duplicate_check",
        "format.decode_check",
        "quality.blur_check",
        "quality.brightness_check",
        "quality.contrast_check",
        "size.aspect_ratio_check",
        "size.dimension_check",
        "size.megapixel_check",
    ]


def test_default_registry_excludes_fastdup_and_near_duplicate() -> None:
    registry = create_default_registry()

    near_duplicate_name = "duplicate." + "near_duplicate_check"
    assert near_duplicate_name not in registry.list_operators()


def test_decode_and_dimension_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    decode_spec = registry.get_operator("format.decode_check")
    dimension_spec = registry.get_operator("size.dimension_check")

    assert decode_spec.required_parameters == ["decode_ok", "decode_error"]
    assert decode_spec.evaluation_columns == ["decode_action", "decode_reason"]
    assert dimension_spec.required_parameters == ["width", "height"]
    assert dimension_spec.evaluation_columns == ["dimension_action", "dimension_reason"]


def test_size_derived_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    aspect_spec = registry.get_operator("size.aspect_ratio_check")
    megapixel_spec = registry.get_operator("size.megapixel_check")

    assert aspect_spec.required_parameters == ["aspect_ratio"]
    assert aspect_spec.evaluation_columns == ["aspect_ratio", "aspect_ratio_action", "aspect_ratio_reason"]
    assert megapixel_spec.required_parameters == ["megapixels"]
    assert megapixel_spec.evaluation_columns == ["megapixels", "megapixel_action", "megapixel_reason"]


def test_quality_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    assert registry.get_operator("quality.blur_check").required_parameters == ["blur_score"]
    assert registry.get_operator("quality.brightness_check").required_parameters == ["brightness_score"]
    assert registry.get_operator("quality.contrast_check").required_parameters == ["contrast_score"]
    assert registry.get_operator("content.blank_image_check").required_parameters == ["blank_score"]


def test_quality_evaluators_return_expected_actions() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["ok", "bad"],
            "blur_score": [200.0, 10.0],
            "brightness_score": [120.0, 5.0],
            "contrast_score": [20.0, 2.0],
            "blank_score": [0.0, 1.0],
        }
    )

    assert registry.get_operator("quality.blur_check").evaluate(frame, {"min_score": 100.0, "action": "review"})[
        "blur_action"
    ].tolist() == ["keep", "review"]
    assert registry.get_operator("quality.brightness_check").evaluate(
        frame, {"min_score": 30.0, "max_score": 225.0, "action": "review"}
    )["brightness_action"].tolist() == ["keep", "review"]
    assert registry.get_operator("quality.contrast_check").evaluate(frame, {"min_score": 10.0, "action": "review"})[
        "contrast_action"
    ].tolist() == ["keep", "review"]
    assert registry.get_operator("content.blank_image_check").evaluate(frame, {"threshold": 0.98, "action": "drop"})[
        "blank_action"
    ].tolist() == ["keep", "drop"]


def test_exact_duplicate_evaluator_drops_non_first_group_members() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "exact_duplicate_group_id": ["exact-h1", "exact-h1", ""],
            "exact_duplicate_count": [2, 2, 1],
        }
    )

    result = registry.get_operator("duplicate.exact_duplicate_check").evaluate(
        frame, {"keep": "first", "action": "drop"}
    )

    assert result["exact_duplicate_action"].tolist() == ["keep", "drop", "keep"]


def test_default_registry_can_find_metadata_computer_for_builtin_parameters() -> None:
    registry = create_default_registry()

    computers = registry.find_computers_for_parameters(
        {
            "decode_ok",
            "decode_error",
            "width",
            "height",
        }
    )

    assert [computer.name for computer in computers] == ["image_metadata_computer"]
