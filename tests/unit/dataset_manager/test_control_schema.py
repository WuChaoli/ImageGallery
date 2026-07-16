from image_gallery.dataset_manager.control import metadata


def test_control_plane_declares_all_mvp_relations() -> None:
    assert set(metadata.tables) == {
        "control.datasets",
        "control.operation_phases",
        "control.operations",
        "control.repo_storage_bindings",
        "control.repos",
        "control.tag_definitions",
        "control.vector_fields",
        "control.vector_validation_items",
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


def test_operation_dataset_identity_can_precede_dataset_registration() -> None:
    operations = metadata.tables["control.operations"]

    assert not operations.c.dataset_id.foreign_keys
