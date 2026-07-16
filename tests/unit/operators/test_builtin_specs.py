import pandas as pd
import pytest

from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_builtin_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "animated",
        "aspect_ratio",
        "blank",
        "blur",
        "border_padding",
        "brightness",
        "contrast",
        "decode",
        "dimension",
        "exact_duplicate",
        "exposure",
        "megapixel",
        "mono_color",
        "noise",
        "orientation",
        "perceptual_duplicate",
        "semantic_duplicate",
    ]


def test_default_registry_excludes_fastdup_and_near_duplicate() -> None:
    registry = create_default_registry()

    near_duplicate_name = "duplicate." + "near_duplicate_check"
    assert near_duplicate_name not in registry.list_operators()


@pytest.mark.parametrize(
    ("operator_name", "default_actions", "caption_columns", "groupby"),
    [
        ("decode", ["drop"], ["decode_reason"], None),
        ("blur", ["drop", "review"], ["blur_score", "blur_reason"], None),
        (
            "perceptual_duplicate",
            ["drop", "review"],
            ["perceptual_duplicate_distance"],
            "perceptual_duplicate_group_id",
        ),
        (
            "semantic_duplicate",
            ["drop", "review"],
            ["semantic_duplicate_score", "semantic_duplicate_nearest_image_id"],
            "semantic_duplicate_group_id",
        ),
    ],
)
def test_builtin_preview_policy_matches_runtime_contract(
    operator_name: str,
    default_actions: list[str],
    caption_columns: list[str],
    groupby: str | None,
) -> None:
    policy = create_default_registry().get_operator(operator_name).preview_policy

    assert policy.default_actions == default_actions
    assert policy.caption_columns == caption_columns
    assert policy.groupby == groupby


def test_decode_and_dimension_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    decode_spec = registry.get_operator("decode")
    dimension_spec = registry.get_operator("dimension")

    assert decode_spec.required_parameters == ["decode_ok", "decode_error"]
    assert decode_spec.evaluation_columns == ["decode_action", "decode_reason"]
    assert dimension_spec.required_parameters == ["width", "height"]
    assert dimension_spec.evaluation_columns == ["dimension_action", "dimension_reason"]


def test_size_derived_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    aspect_spec = registry.get_operator("aspect_ratio")
    megapixel_spec = registry.get_operator("megapixel")

    assert aspect_spec.required_parameters == ["aspect_ratio"]
    assert aspect_spec.evaluation_columns == ["aspect_ratio", "aspect_ratio_action", "aspect_ratio_reason"]
    assert megapixel_spec.required_parameters == ["megapixels"]
    assert megapixel_spec.evaluation_columns == ["megapixels", "megapixel_action", "megapixel_reason"]


def test_quality_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    assert registry.get_operator("blur").required_parameters == ["blur_score"]
    assert registry.get_operator("brightness").required_parameters == ["brightness_score"]
    assert registry.get_operator("contrast").required_parameters == ["contrast_score"]
    assert registry.get_operator("blank").required_parameters == ["blank_score"]


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

    assert registry.get_operator("blur").evaluate(frame, {"min_score": 100.0, "action": "review"})[
        "blur_action"
    ].tolist() == ["keep", "review"]
    assert registry.get_operator("brightness").evaluate(
        frame, {"min_score": 30.0, "max_score": 225.0, "action": "review"}
    )["brightness_action"].tolist() == ["keep", "review"]
    assert registry.get_operator("contrast").evaluate(frame, {"min_score": 10.0, "action": "review"})[
        "contrast_action"
    ].tolist() == ["keep", "review"]
    assert registry.get_operator("blank").evaluate(frame, {"threshold": 0.98, "action": "drop"})[
        "blank_action"
    ].tolist() == ["keep", "drop"]


def test_light_quality_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    assert registry.get_operator("exposure").required_parameters == [
        "dark_pixel_ratio",
        "bright_pixel_ratio",
        "clipped_pixel_ratio",
    ]
    assert registry.get_operator("noise").required_parameters == ["noise_score"]
    assert registry.get_operator("mono_color").required_parameters == ["mono_color_score"]
    assert registry.get_operator("border_padding").required_parameters == [
        "border_padding_ratio",
        "border_padding_sides",
        "border_padding_color",
    ]
    assert registry.get_operator("animated").required_parameters == ["frame_count", "animated"]
    assert registry.get_operator("orientation").required_parameters == [
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

    assert registry.get_operator("exposure").evaluate(frame, {})["exposure_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("noise").evaluate(frame, {})["noise_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("mono_color").evaluate(frame, {})["mono_color_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("border_padding").evaluate(frame, {})["border_padding_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("animated").evaluate(frame, {})["animated_action"].tolist() == [
        "keep",
        "review",
    ]
    assert registry.get_operator("orientation").evaluate(frame, {})["orientation_action"].tolist() == [
        "keep",
        "review",
    ]


def test_exact_duplicate_evaluator_drops_non_first_group_members() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "exact_duplicate_group_id": ["exact-h1", "exact-h1", ""],
            "exact_duplicate_count": [2, 2, 1],
        }
    )

    result = registry.get_operator("exact_duplicate").evaluate(frame, {"keep": "first", "action": "drop"})

    assert result["exact_duplicate_action"].tolist() == ["keep", "drop", "keep"]


def test_perceptual_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("perceptual_duplicate")

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

    result = registry.get_operator("perceptual_duplicate").evaluate(
        frame,
        {"max_distance": 4, "keep": "first", "action": "drop"},
    )

    assert result["perceptual_duplicate_action"].tolist() == ["keep", "drop", "keep"]
    assert result.loc[1, "perceptual_duplicate_reason"] == "duplicate in group perceptual-a distance 3"


def test_semantic_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("semantic_duplicate")

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

    drop_result = registry.get_operator("semantic_duplicate").evaluate(frame, {"keep": "first", "action": "drop"})
    review_result = registry.get_operator("semantic_duplicate").evaluate(frame, {"keep": "first", "action": "review"})

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


def test_builtin_specs_have_preview_policy() -> None:
    registry = create_default_registry()

    for spec in registry.list_operator_specs():
        assert spec.preview_policy is not None


def test_duplicate_specs_group_preview_by_duplicate_group() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("semantic_duplicate")

    assert spec.preview_policy.groupby == "semantic_duplicate_group_id"
    assert spec.preview_policy.include_group_context is True
