from pathlib import Path

from image_gallery.annotations._pascal_voc import read_pascal_voc_xml, write_pascal_voc_xml
from image_gallery.annotations._tabular_values import annotation_list, require_positive_int


class ArrayLike:
    def tolist(self) -> list[dict[str, object]]:
        return [{"label": "person"}]


def test_labelimg_tabular_value_boundary_normalizes_parquet_like_values() -> None:
    assert annotation_list(ArrayLike()) == [{"label": "person"}]
    assert require_positive_int("12", "width") == 12


def test_private_pascal_voc_boundary_round_trips_empty_annotation_file(tmp_path: Path) -> None:
    xml_path = tmp_path / "img-1.xml"

    write_pascal_voc_xml(
        xml_path=xml_path,
        folder="images",
        filename="img-1.png",
        image_path=tmp_path / "images" / "img-1.png",
        width=10,
        height=8,
        depth=3,
        annotations=[],
    )

    parsed = read_pascal_voc_xml(xml_path)
    assert (parsed.filename, parsed.width, parsed.height, parsed.annotations) == ("img-1.png", 10, 8, [])
