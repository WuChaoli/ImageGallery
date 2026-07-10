from pathlib import Path

import pandas as pd
from notebooks._helpers.cleaning_configs import get_cleaning_v3_non_semantic_all_operator_configs
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.events import RuntimeEvent
from image_gallery.dataset import Dataset


def _write_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color=color).save(path)


def test_basic_cleaner_exports_builtin_views_and_preserves_counts(tmp_path: Path) -> None:
    ok = tmp_path / "ok.png"
    small = tmp_path / "small.png"
    broken = tmp_path / "broken.jpg"
    _write_image(ok, (16, 16), (10, 20, 30))
    _write_image(small, (4, 4), (200, 210, 220))
    broken.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "small", "bad"],
                "image_uri": [str(ok), str(small), str(broken)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner(
        [
            {"format.decode_check": {"action": "drop"}},
            {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
        ]
    )
    result = cleaner.run(dataset)

    full = result.export("full", str(tmp_path / "full.parquet"))
    clean = result.export("clean", str(tmp_path / "clean.parquet"))
    review = result.export("review", str(tmp_path / "review.parquet"))
    dropped = result.export("dropped", str(tmp_path / "dropped.parquet"))
    parameters = result.export("parameters", str(tmp_path / "parameters.parquet"))
    evaluations = result.export("evaluations", str(tmp_path / "evaluations.parquet"))
    preview = result.preview()

    assert full.count() == 3
    assert clean.count() == 1
    assert review.count() == 1
    assert dropped.count() == 1
    assert preview.restricted_count == 0
    assert {"image_id", "image_uri", "width", "height", "decode_error", "decode_ok"}.issubset(
        parameters.to_frame().columns
    )
    assert evaluations.count() == 3


def test_basic_cleaner_writes_html_preview(tmp_path: Path) -> None:
    ok = tmp_path / "ok.png"
    broken = tmp_path / "broken.jpg"
    _write_image(ok, (16, 16), (10, 20, 30))
    broken.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "bad"],
                "image_uri": [str(ok), str(broken)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner([{"format.decode_check": {"action": "drop"}}])
    result = cleaner.run(dataset)

    output_path = result.preview_html(
        tmp_path / "preview.html",
        action="drop",
        caption_columns=["image_id"],
    )

    html = output_path.read_text(encoding="utf-8")
    assert output_path == tmp_path / "preview.html"
    assert "Cleaning Preview" in html
    assert "bad" in html
    assert "final_action: drop" not in html


def test_toml_full_runtime_exports_previews_and_cleanup(tmp_path: Path) -> None:
    ok = tmp_path / "ok.png"
    duplicate = tmp_path / "duplicate.png"
    small = tmp_path / "small.png"
    blank = tmp_path / "blank.png"
    border = tmp_path / "border.png"
    broken = tmp_path / "broken.jpg"
    _write_image(ok, (32, 32), (10, 80, 130))
    duplicate.write_bytes(ok.read_bytes())
    _write_image(small, (4, 4), (200, 210, 220))
    _write_image(blank, (32, 32), (255, 255, 255))
    border_image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    for x in range(10, 22):
        for y in range(10, 22):
            border_image.putpixel((x, y), (40, 80, 140))
    border_image.save(border)
    broken.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "dupe", "small", "blank", "border", "bad"],
                "image_uri": [
                    str(ok),
                    str(duplicate),
                    str(small),
                    str(blank),
                    str(border),
                    str(broken),
                ],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    operator_configs = get_cleaning_v3_non_semantic_all_operator_configs()
    operator_names = [next(iter(item)) for item in operator_configs]
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text(
        "[cleaner]\noperators = ["
        + ", ".join(f'\"{operator_name}\"' for operator_name in operator_names)
        + "]\n",
        encoding="utf-8",
    )
    events: list[RuntimeEvent] = []

    cleaner = BasicCleaner.from_toml(recipe_path)
    execution = cleaner.compile()
    result = execution.run(dataset, progress=events.append)

    assert result.status() == "completed"
    assert "node_started" in [event.event_type for event in events]
    assert set(operator_names).issubset(set(result.state()["operator_name"]))

    previews_dir = tmp_path / "previews"
    for operator_name in operator_names:
        output_path = result.preview_html(
            previews_dir / f"{operator_name.replace('.', '__')}.html",
            operator_name=operator_name,
            actions="full",
            max_rows=6,
        )
        assert output_path.exists()
        assert "Cleaning Preview" in output_path.read_text(encoding="utf-8")

    exports_dir = tmp_path / "exports"
    parameter_table_path = result.export_table("parameter", exports_dir / "parameter_table.parquet")
    evaluation_table_path = result.export_table("evaluation", exports_dir / "evaluation_table.parquet")
    full = result.export("full", exports_dir / "full.parquet")
    clean = result.export("clean", exports_dir / "clean.parquet")
    review = result.export("review", exports_dir / "review.parquet")
    dropped = result.export("dropped", exports_dir / "dropped.parquet")
    relation_path = result.export_relations("duplicate_pairs", exports_dir / "duplicate_pairs.parquet")
    debug_bundle = result.export_debug_bundle(exports_dir / "debug_bundle.zip")

    assert pd.read_parquet(parameter_table_path)["image_id"].tolist()
    assert pd.read_parquet(evaluation_table_path)["image_id"].tolist()
    assert full.count() == 6
    assert clean.count() + review.count() + dropped.count() == 6
    assert relation_path.exists()
    assert debug_bundle.exists()

    result.cleanup()

    assert result.status() == "running"
    assert exports_dir.exists()
    assert previews_dir.exists()
