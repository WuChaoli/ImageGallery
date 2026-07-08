import pandas as pd

from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_builtin_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "content.blank_image_check",
        "content.border_padding_check",
        "content.mono_color_check",
        "duplicate.exact_duplicate_check",
        "duplicate.perceptual_duplicate_check",
        "duplicate.semantic_duplicate_check",
        "format.animated_image_check",
        "format.decode_check",
        "metadata.orientation_check",
        "quality.blur_check",
        "quality.brightness_check",
        "quality.contrast_check",
        "quality.exposure_check",
        "quality.noise_check",
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


def test_light_quality_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    assert registry.get_operator("quality.exposure_check").required_parameters == [
        "dark_pixel_ratio",
        "bright_pixel_ratio",
        "clipped_pixel_ratio",
    ]
    assert registry.get_operator("quality.noise_check").required_parameters == ["noise_score"]
    assert registry.get_operator("content.mono_color_check").required_parameters == ["mono_color_score"]
    assert registry.get_operator("content.border_padding_check").required_parameters == [
        "border_padding_ratio",
        "border_padding_sides",
        "border_padding_color",
    ]
    assert registry.get_operator("format.animated_image_check").required_parameters == ["frame_count", "animated"]
    assert registry.get_operator("metadata.orientation_check").required_parameters == [
        "exif_orientation",
        "orientation_risk",
    ]


def test_light_quality_evaluators_return_expected_actions() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["ok", "bad"],
            "dark_pixel_ratio": [0.01, 0.99],
            "bright_pixel_ratio": [0.01, 0.0],
            "clipped_pixel_ratio": [0.01, 0.99],
            "noise_score": [0.1, 0.9],
            "mono_color_score": [0.2, 0.99],
            "border_padding_ratio": [0.0, 0.5],
            "border_padding_sides": ["", "top,bottom"],
            "border_padding_color": ["unknown", "white"],
            "frame_count": [1, 3],
            "animated": [False, True],
            "exif_orientation": [pd.NA, 6],
            "orientation_risk": [False, True],
        }
    )

    assert registry.get_operator("quality.exposure_check").evaluate(frame, {})["exposure_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("quality.noise_check").evaluate(frame, {})["noise_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("content.mono_color_check").evaluate(frame, {})["mono_color_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("content.border_padding_check").evaluate(frame, {})[
        "border_padding_action"
    ].tolist() == ["keep", "review"]
    assert registry.get_operator("format.animated_image_check").evaluate(frame, {})["animated_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("metadata.orientation_check").evaluate(frame, {})[
        "orientation_action"
    ].tolist() == ["keep", "review"]


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


def test_perceptual_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("duplicate.perceptual_duplicate_check")

    assert spec.default_config == {"max_distance": 10, "keep": "first", "action": "drop"}
    assert spec.required_parameters == [
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
    ]
    assert spec.evaluation_columns == [
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
        "perceptual_duplicate_action",
        "perceptual_duplicate_reason",
    ]


def test_perceptual_duplicate_evaluator_drops_non_first_group_members() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "perceptual_duplicate_group_id": ["perceptual-a", "perceptual-a", ""],
            "perceptual_duplicate_count": [2, 2, 1],
            "perceptual_duplicate_distance": [0, 3, pd.NA],
        }
    )

    result = registry.get_operator("duplicate.perceptual_duplicate_check").evaluate(
        frame,
        {"max_distance": 4, "keep": "first", "action": "drop"},
    )

    assert result["perceptual_duplicate_action"].tolist() == ["keep", "drop", "keep"]
    assert result.loc[1, "perceptual_duplicate_reason"] == "duplicate in group perceptual-a distance 3"


def test_semantic_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("duplicate.semantic_duplicate_check")

    assert spec.required_parameters == [
        "semantic_duplicate_group_id",
        "semantic_duplicate_count",
        "semantic_duplicate_score",
        "semantic_duplicate_nearest_image_id",
    ]
    assert spec.evaluation_columns == [
        "semantic_duplicate_group_id",
        "semantic_duplicate_count",
        "semantic_duplicate_score",
        "semantic_duplicate_nearest_image_id",
        "semantic_duplicate_action",
        "semantic_duplicate_reason",
    ]
    assert spec.default_config["provider"] == "onnx_dinov2_small"
    assert spec.default_config["model_id"] == "onnx-community/dinov2-small-ONNX"


def test_semantic_duplicate_evaluator_supports_drop_and_review() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "semantic_duplicate_group_id": ["semantic-first", "semantic-first", ""],
            "semantic_duplicate_count": [2, 2, 1],
            "semantic_duplicate_score": [1.0, 0.95, pd.NA],
            "semantic_duplicate_nearest_image_id": ["", "first", ""],
        }
    )

    drop_result = registry.get_operator("duplicate.semantic_duplicate_check").evaluate(
        frame, {"keep": "first", "action": "drop"}
    )
    review_result = registry.get_operator("duplicate.semantic_duplicate_check").evaluate(
        frame, {"keep": "first", "action": "review"}
    )

    assert drop_result["semantic_duplicate_action"].tolist() == ["keep", "drop", "keep"]
    assert review_result["semantic_duplicate_action"].tolist() == ["keep", "review", "keep"]
    assert "semantic-first" in drop_result.loc[1, "semantic_duplicate_reason"]
    assert "0.9500" in drop_result.loc[1, "semantic_duplicate_reason"]


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
