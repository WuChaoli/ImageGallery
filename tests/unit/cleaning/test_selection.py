import pytest

from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry


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
