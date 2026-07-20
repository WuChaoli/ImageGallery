from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pyarrow as pa
import pytest

from image_gallery.dataset_manager import (
    ColumnSpec,
    DatasetManager,
    ListFieldType,
    PrimitiveFieldType,
    StructField,
    StructFieldType,
    ValidationError,
)
from image_gallery.dataset_manager._physical_schema import (
    column_spec_from_arrow,
    column_spec_from_iceberg,
    column_spec_to_arrow,
    column_spec_to_iceberg,
)
from image_gallery.storage_manager import StorageManager


def annotation_column() -> ColumnSpec:
    bbox = StructFieldType(
        (
            StructField("x_min", "double", required=True),
            StructField("y_min", "double", required=True),
            StructField("x_max", "double", required=True),
            StructField("y_max", "double", required=True),
        )
    )
    annotation = StructFieldType(
        (
            StructField("label", "string", required=True),
            StructField("bbox", bbox, required=True),
            StructField("format", "string", required=True),
            StructField("source", "string"),
            StructField("difficult", "integer"),
            StructField("truncated", "integer"),
            StructField("pose", "string"),
        )
    )
    return ColumnSpec("annotations", ListFieldType(annotation, element_required=True))


def test_recursive_schema_dtos_are_frozen_and_normalize_sequences_and_scalar_names() -> None:
    fields = [StructField(" label ", "string", required=True)]
    field_type = StructFieldType(fields)
    column = ColumnSpec(" annotations ", ListFieldType(field_type, element_required=True))

    fields.append(StructField("ignored", "string"))

    assert column.name == "annotations"
    assert isinstance(column.field_type, ListFieldType)
    assert column.field_type.element_type == StructFieldType(
        (StructField("label", PrimitiveFieldType("string"), required=True),)
    )
    with pytest.raises(FrozenInstanceError):
        column.name = "changed"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PrimitiveFieldType("object"),
        lambda: StructFieldType(()),
        lambda: StructFieldType((StructField("name", "string"), StructField(" NAME ", "string"))),
        lambda: StructField(" ", "string"),
        lambda: ListFieldType("string", element_required=cast(bool, "yes")),
        lambda: ColumnSpec(" ", "string"),
    ],
)
def test_recursive_schema_dtos_reject_invalid_contracts(factory) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    with pytest.raises(ValidationError):
        factory()


def test_column_spec_json_round_trip_is_deterministic_and_has_no_field_ids() -> None:
    column = annotation_column()

    payload = column.to_dict()

    assert ColumnSpec.from_dict(payload) == column
    assert payload == column.to_dict()
    assert "field_id" not in repr(payload)


def test_column_spec_round_trips_arrow_and_iceberg_without_exposing_ids() -> None:
    column = annotation_column()

    arrow_field = column_spec_to_arrow(column)
    iceberg_field = column_spec_to_iceberg(column)

    assert column_spec_from_arrow(arrow_field) == column
    assert column_spec_from_iceberg(iceberg_field) == column
    assert pa.types.is_list(arrow_field.type)
    assert arrow_field.type.value_field.nullable is False


def test_column_spec_from_arrow_accepts_pyiceberg_large_string_and_large_list() -> None:
    field = pa.field(
        "labels",
        pa.large_list(pa.field("element", pa.large_string(), nullable=False)),
        nullable=True,
    )

    assert column_spec_from_arrow(field) == ColumnSpec(
        "labels",
        ListFieldType("string", element_required=True),
    )


def test_column_spec_from_dict_rejects_recursive_mapping_as_validation_error() -> None:
    recursive_type: dict[str, object] = {
        "kind": "list",
        "element_required": False,
    }
    recursive_type["element_type"] = recursive_type

    with pytest.raises(ValidationError, match="finite and acyclic"):
        ColumnSpec.from_dict(
            {
                "name": "recursive",
                "field_type": recursive_type,
                "required": False,
            }
        )


def test_dataset_schema_returns_typed_columns_and_accepts_column_spec(tmp_path: Path) -> None:
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=StorageManager())
    dataset = manager.create_repo(name="Vision").create_dataset(name="Raw")

    view = dataset.schema.add_column(branch="main", base=dataset.open_branch(), column=annotation_column())

    columns = dataset.schema.list_columns()
    assert dataset.schema.get_column(name="annotations") == annotation_column()
    assert [column.name for column in columns] == [
        "asset_id",
        "storage_prefix_id",
        "relative_path",
        "source_uri",
        "tag_ids",
        "annotations",
    ]
    assert columns[4] == ColumnSpec(
        "tag_ids",
        ListFieldType("string", element_required=True),
        required=True,
    )
    assert view.snapshot_id is None


def test_dataset_schema_preserves_legacy_scalar_add_column_call(tmp_path: Path) -> None:
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=StorageManager())
    dataset = manager.create_repo(name="Vision").create_dataset(name="Raw")

    dataset.schema.add_column(
        branch="main",
        base=dataset.open_branch(),
        name="split",
        field_type="string",
    )

    assert dataset.schema.get_column(name="split") == ColumnSpec("split", PrimitiveFieldType("string"))


def test_dataset_schema_rejects_casefold_duplicate_physical_column(tmp_path: Path) -> None:
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=StorageManager())
    dataset = manager.create_repo(name="Vision").create_dataset(name="Raw")
    current = dataset.schema.add_column(
        branch="main",
        base=dataset.open_branch(),
        name="split",
        field_type="string",
    )

    with pytest.raises(ValidationError):
        dataset.schema.add_column(
            branch="main",
            base=current,
            name=" Split ",
            field_type="long",
        )
