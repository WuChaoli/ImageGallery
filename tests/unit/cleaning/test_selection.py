import pytest

from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.spec import ConfiguredOperatorSpec


def test_select_all_expands_registry_order() -> None:
    selected = select_operators("ALL", create_default_registry())

    assert "format.decode_check" in [item.operator_name for item in selected]
    assert "duplicate.semantic_duplicate_check" in [item.operator_name for item in selected]


def test_select_category_expands_matching_operators() -> None:
    selected = select_operators(["QUALITY"], create_default_registry())

    assert {item.spec.category for item in selected} == {"quality"}
    assert "quality.blur_check" in [item.operator_name for item in selected]


def test_select_name_and_category_deduplicates() -> None:
    selected = select_operators(["quality.blur_check", "QUALITY"], create_default_registry())

    names = [item.operator_name for item in selected]
    assert names.count("quality.blur_check") == 1


def test_select_unknown_category_has_helpful_error() -> None:
    with pytest.raises(ValueError, match="available categories"):
        select_operators(["NOT_A_CATEGORY"], create_default_registry())


def test_select_operator_spec_registers_it_and_uses_default_config() -> None:
    registry = create_default_registry()
    spec = registry.get_operator("quality.blur_check")
    custom_spec = type(spec)(
        name="custom.blur_check",
        category=spec.category,
        required_parameters=spec.required_parameters,
        evaluation_columns=spec.evaluation_columns,
        default_config={"min_score": 42.0, "action": "review"},
        action_column=spec.action_column,
        reason_column=spec.reason_column,
        evaluator=spec.evaluator,
        preview_policy=spec.preview_policy,
    )

    selected = select_operators([custom_spec], registry)

    assert selected[0].operator_name == "custom.blur_check"
    assert selected[0].config["min_score"] == 42.0
    assert selected[0].source == "python"
    assert registry.get_operator("custom.blur_check") is custom_spec


def test_select_configured_operator_spec_preserves_config_and_source() -> None:
    registry = create_default_registry()
    spec = registry.get_operator("quality.blur_check")
    custom_spec = type(spec)(
        name="custom.configured_blur_check",
        category=spec.category,
        required_parameters=spec.required_parameters,
        evaluation_columns=spec.evaluation_columns,
        default_config=spec.default_config,
        action_column=spec.action_column,
        reason_column=spec.reason_column,
        evaluator=spec.evaluator,
        preview_policy=spec.preview_policy,
    )
    configured = ConfiguredOperatorSpec.from_spec(custom_spec, {"min_score": 42.0}, source="python")

    selected = select_operators([configured], registry)

    assert selected == [configured]


def test_select_duplicate_temporary_spec_requires_override() -> None:
    registry = create_default_registry()
    spec = registry.get_operator("quality.blur_check")

    with pytest.raises(ValueError, match="already exists"):
        select_operators([spec], registry)
