from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_only_first_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "format.decode_check",
        "size.dimension_check",
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
