from pathlib import Path

import pandas as pd

from image_gallery.annotations.labelimg import voc_bbox_to_annotation
from image_gallery.dataset_manager import (
    ColumnSpec,
    DatasetManager,
    ListFieldType,
    StructField,
    StructFieldType,
)
from image_gallery.storage_manager import StorageManager


def annotation_column() -> ColumnSpec:
    """返回 Annotation v1 的 DatasetManager 物理列定义。"""
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


def test_annotation_v1_round_trips_commit_checkpoint_and_branch(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    base = dataset.schema.add_column(
        branch="main",
        base=dataset.open_branch(),
        column=annotation_column(),
    )

    full = voc_bbox_to_annotation(
        label="person",
        xmin=10,
        ymin=20,
        xmax=60,
        ymax=70,
        width=100,
        height=100,
        difficult=1,
        truncated=1,
        pose="Frontal",
    )
    partial = voc_bbox_to_annotation(
        label="car",
        xmin=5,
        ymin=10,
        xmax=40,
        ymax=50,
        width=80,
        height=100,
    )
    for optional_name in ("source", "difficult", "truncated", "pose"):
        partial.pop(optional_name)
    expected_partial = {
        **partial,
        "source": None,
        "difficult": None,
        "truncated": None,
        "pose": None,
    }

    first = storage.write_managed(prefix_id=prefix.prefix_id, data=b"first")
    second = storage.write_managed(prefix_id=prefix.prefix_id, data=b"second")
    rows = [
        {
            "asset_id": first.asset_id,
            "storage_prefix_id": first.storage_prefix_id,
            "relative_path": first.relative_path,
            "source_uri": None,
            "tag_ids": [],
            "annotations": [full, partial],
        },
        {
            "asset_id": second.asset_id,
            "storage_prefix_id": second.storage_prefix_id,
            "relative_path": second.relative_path,
            "source_uri": None,
            "tag_ids": [],
            "annotations": [],
        },
    ]

    committed = dataset.commit(branch="main", base=base, frame=pd.DataFrame(rows)).view
    checkpoint = dataset.create_checkpoint(name="annotated", source=committed)
    branch = dataset.create_branch(name="review", source=checkpoint)

    expected = {
        first.asset_id: [full, expected_partial],
        second.asset_id: [],
    }
    for view in (committed, checkpoint, branch):
        actual = {str(row["asset_id"]): row["annotations"] for row in view.scan().to_dict(orient="records")}
        assert actual == expected


def test_annotation_v1_round_trips_materialize(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Raw")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    annotation = voc_bbox_to_annotation(
        label="person",
        xmin=10,
        ymin=20,
        xmax=60,
        ymax=70,
        width=100,
        height=100,
    )
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    frame = fixed.scan()
    frame["annotations"] = pd.Series([[annotation]], dtype=object)

    result = repo.materialize_dataset(
        source=fixed,
        name="Annotated",
        frame=frame,
        schema_additions=(annotation_column(),),
    )

    assert result.view.scan().iloc[0]["annotations"] == [annotation]
    assert result.dataset.schema.get_column(name="annotations") == annotation_column()
