from pathlib import Path

import pytest

from image_gallery.annotations.labelimg import (
    read_pascal_voc_xml,
    relative_bbox_to_voc_bbox,
    voc_bbox_to_annotation,
    write_pascal_voc_xml,
)


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
