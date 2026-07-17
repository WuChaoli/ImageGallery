from image_gallery.dataset_manager.control import metadata


def test_control_plane_declares_all_mvp_relations() -> None:
    assert set(metadata.tables) == {
        "control.datasets",
        "control.operation_phases",
        "control.operations",
        "control.repo_storage_bindings",
        "control.repos",
        "control.storage_prefixes",
        "control.tag_definitions",
        "control.vector_fields",
        "vectors.asset_vectors",
        "vectors.pending_asset_vectors",
    }


def test_vector_rows_have_repo_field_asset_identity() -> None:
    for table_name in ("vectors.asset_vectors", "vectors.pending_asset_vectors"):
        table = metadata.tables[table_name]
        assert {column.name for column in table.primary_key.columns} >= {
            "repo_id",
            "vector_field_id",
            "asset_id",
        }


def test_vector_rows_reference_vector_field_within_same_repo() -> None:
    vector_fields = metadata.tables["control.vector_fields"]
    unique_column_sets = [{column.name for column in constraint.columns} for constraint in vector_fields.constraints]
    assert {"repo_id", "vector_field_id"} in unique_column_sets

    for table_name in ("vectors.asset_vectors", "vectors.pending_asset_vectors"):
        table = metadata.tables[table_name]
        foreign_key_column_sets = [
            {element.parent.name for element in constraint.elements} for constraint in table.foreign_key_constraints
        ]
        assert {"repo_id", "vector_field_id"} in foreign_key_column_sets


def test_operation_dataset_identity_can_precede_dataset_registration() -> None:
    operations = metadata.tables["control.operations"]

    assert not operations.c.dataset_id.foreign_keys
