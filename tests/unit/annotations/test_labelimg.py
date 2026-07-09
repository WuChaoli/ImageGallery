from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.annotations import LabelImgExporter, LabelImgLoader
from image_gallery.annotations.labelimg import (
    read_pascal_voc_xml,
    relative_bbox_to_voc_bbox,
    voc_bbox_to_annotation,
    write_pascal_voc_xml,
)
from image_gallery.dataset import Dataset


def test_relative_bbox_to_voc_bbox_uses_image_dimensions() -> None:
    annotation = {
        "label": "person",
        "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
        "format": "relative_xyxy",
    }

    assert relative_bbox_to_voc_bbox(annotation, width=100, height=80) == (10, 20, 60, 60)


def test_voc_bbox_to_annotation_stores_relative_coordinates() -> None:
    annotation = voc_bbox_to_annotation(
        label="person",
        xmin=10,
        ymin=20,
        xmax=60,
        ymax=60,
        width=100,
        height=80,
        difficult=1,
        truncated=0,
        pose="Frontal",
    )

    assert annotation == {
        "label": "person",
        "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
        "format": "relative_xyxy",
        "source": "labelimg_pascal_voc",
        "difficult": 1,
        "truncated": 0,
        "pose": "Frontal",
    }


def test_pascal_voc_xml_round_trips_objects(tmp_path: Path) -> None:
    xml_path = tmp_path / "img-1.xml"
    image_path = tmp_path / "images" / "img-1.png"
    image_path.parent.mkdir()

    write_pascal_voc_xml(
        xml_path=xml_path,
        folder="images",
        filename="img-1.png",
        image_path=image_path,
        width=100,
        height=80,
        depth=3,
        annotations=[
            {
                "label": "person",
                "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                "format": "relative_xyxy",
                "difficult": 1,
            }
        ],
    )

    parsed = read_pascal_voc_xml(xml_path)

    assert parsed.filename == "img-1.png"
    assert parsed.width == 100
    assert parsed.height == 80
    assert parsed.annotations == [
        {
            "label": "person",
            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
            "format": "relative_xyxy",
            "source": "labelimg_pascal_voc",
            "difficult": 1,
            "truncated": 0,
            "pose": "Unspecified",
        }
    ]


def test_invalid_relative_bbox_is_rejected() -> None:
    annotation = {
        "label": "person",
        "bbox": {"x_min": 0.8, "y_min": 0.1, "x_max": 0.2, "y_max": 0.3},
        "format": "relative_xyxy",
    }

    with pytest.raises(ValueError, match="invalid bbox"):
        relative_bbox_to_voc_bbox(annotation, width=100, height=80)


def _write_image(path: Path, size: tuple[int, int] = (10, 8), color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    Image.new("RGB", size, color=color).save(path)
    return path.read_bytes()


def test_labelimg_exporter_writes_images_dataset_and_existing_xml(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image_bytes = _write_image(image_path, size=(100, 80))
    dataset = Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": str(image_path),
                    "width": 100,
                    "height": 80,
                    "file_extension": ".png",
                    "source_uri": "/camera/source.png",
                    "annotations": [
                        {
                            "label": "person",
                            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                            "format": "relative_xyxy",
                        }
                    ],
                }
            ]
        ),
        str(tmp_path / "raw.parquet"),
    )
    output_dir = tmp_path / "labelimg"

    result = dataset.export(LabelImgExporter(output_dir))

    assert result.output_dir == str(output_dir)
    assert result.image_count == 1
    assert result.annotation_count == 1
    assert (output_dir / "raw.parquet").exists()
    assert (output_dir / "images" / "img-1.png").read_bytes() == image_bytes
    parsed = read_pascal_voc_xml(output_dir / "annotations" / "img-1.xml")
    assert parsed.filename == "img-1.png"
    assert parsed.annotations[0]["label"] == "person"


def test_labelimg_exporter_rejects_existing_output_without_overwrite(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    _write_image(image_path)
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": str(image_path), "width": 10, "height": 8}]),
        str(tmp_path / "raw.parquet"),
    )
    output_dir = tmp_path / "labelimg"
    output_dir.mkdir()

    with pytest.raises(FileExistsError):
        dataset.export(LabelImgExporter(output_dir))


def test_labelimg_loader_writes_labeled_dataset_with_relative_annotations(tmp_path: Path) -> None:
    input_dir = tmp_path / "task"
    annotations_dir = input_dir / "annotations"
    annotations_dir.mkdir(parents=True)
    Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": str(tmp_path / "img-1.png"),
                    "width": 100,
                    "height": 80,
                }
            ]
        ),
        str(input_dir / "raw.parquet"),
    )
    write_pascal_voc_xml(
        xml_path=annotations_dir / "img-1.xml",
        folder="images",
        filename="img-1.png",
        image_path=input_dir / "images" / "img-1.png",
        width=100,
        height=80,
        depth=3,
        annotations=[
            {
                "label": "person",
                "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                "format": "relative_xyxy",
            }
        ],
    )

    dataset = Dataset.load(LabelImgLoader(input_dir))

    frame = dataset.to_frame()
    assert dataset.dataset_path == str(input_dir / "labeled.parquet")
    assert frame.loc[0, "annotations"] == [
        {
            "label": "person",
            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
            "format": "relative_xyxy",
            "source": "labelimg_pascal_voc",
            "difficult": 0,
            "truncated": 0,
            "pose": "Unspecified",
        }
    ]


def test_labelimg_loader_rejects_unknown_xml_image_id(tmp_path: Path) -> None:
    input_dir = tmp_path / "task"
    annotations_dir = input_dir / "annotations"
    annotations_dir.mkdir(parents=True)
    Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/img-1.png", "width": 100, "height": 80}]),
        str(input_dir / "raw.parquet"),
    )
    write_pascal_voc_xml(
        xml_path=annotations_dir / "unknown.xml",
        folder="images",
        filename="unknown.png",
        image_path=input_dir / "images" / "unknown.png",
        width=100,
        height=80,
        depth=3,
        annotations=[],
    )

    with pytest.raises(ValueError, match="no matching image_id"):
        Dataset.load(LabelImgLoader(input_dir))
