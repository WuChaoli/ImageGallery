import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.cleaning.result import CleanerResult
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry


def _build_image(path: Path, color: tuple[int, int, int]) -> str:
    """生成一张固定颜色的小图并返回其路径字符串。"""
    Image.new("RGB", (2, 2), color=color).save(path)
    return str(path)


def _run_for_operator_actions(tmp_path: Path) -> CleanerResult:
    """构造一个最小运行结果，包含操作列与 final_action 冲突的场景。"""
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    manifests_dir = run_dir / "manifests"
    tables_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    first_image = _build_image(tmp_path / "first.png", (255, 0, 0))
    second_image = _build_image(tmp_path / "second.png", (0, 255, 0))

    pd.DataFrame(
        {
            "image_id": ["img-drop", "img-keep"],
            "image_uri": [first_image, second_image],
            "final_action": ["keep", "drop"],
            "final_reason": ["", ""],
            "triggered_operator_names": ["decode", ""],
            "decode_action": ["drop", "keep"],
            "decode_reason": ["decode failure", ""],
        }
    ).to_parquet(tables_dir / "evaluation_table.parquet", index=False)
    pd.DataFrame(
        {
            "image_id": ["img-drop", "img-keep"],
            "image_uri": [first_image, second_image],
        }
    ).to_parquet(tables_dir / "parameter_table.parquet", index=False)
    (manifests_dir / "operator_outputs.json").write_text(
        json.dumps(
            {
                "decode": ["decode_action", "decode_reason"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (manifests_dir / "parameter_manifest.json").write_text("{}", encoding="utf-8")
    return CleanerResult(run_id="run-1", cache_root=tmp_path)


def test_result_preview_html_filters_operator_actions(tmp_path: Path) -> None:
    result = _run_for_operator_actions(tmp_path)
    output = result.preview_html(
        tmp_path / "decode_drop.html",
        operator_name="decode",
        actions="drop",
    )

    html = output.read_text(encoding="utf-8")
    assert "first.png" in html
    assert "second.png" not in html


def test_result_preview_html_operator_actions_clean_maps_to_keep(tmp_path: Path) -> None:
    result = _run_for_operator_actions(tmp_path)
    output = result.preview_html(
        tmp_path / "decode_keep.html",
        operator_name="decode",
        actions="clean",
    )

    html = output.read_text(encoding="utf-8")
    assert "second.png" in html
    assert "first.png" not in html


def test_result_preview_html_full_without_operator_action_filter(tmp_path: Path) -> None:
    result = _run_for_operator_actions(tmp_path)
    output = result.preview_html(
        tmp_path / "decode_full.html",
        operator_name="decode",
        actions="full",
    )

    html = output.read_text(encoding="utf-8")
    assert "first.png" in html
    assert "second.png" in html


def test_result_preview_html_uses_execution_preview_policies(tmp_path: Path) -> None:
    def custom_registry() -> OperatorRegistry:
        registry = create_default_registry()
        registry.register_operator(
            replace(
                registry.get_operator("decode"),
                preview_policy=PreviewPolicy(max_rows=1, columns_per_row=1),
            )
        )
        return registry

    first = _build_image(tmp_path / "first.png", (20, 20, 20))
    second = _build_image(tmp_path / "second.png", (40, 40, 40))
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["first", "second"],
                "image_uri": [first, second],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner([{"decode": {}}], registry=custom_registry())
    result = cleaner.run(dataset)
    output = result.preview_html(
        tmp_path / "preview.html",
        operator_name="decode",
    ).read_text(encoding="utf-8")

    assert "first.png" in output
    assert "second.png" not in output
    assert "grid-template-columns: repeat(1, minmax(0, 1fr));" in output

    output_all = result.preview_html(
        tmp_path / "preview_all.html",
        operator_name="decode",
        max_rows=2,
    ).read_text(encoding="utf-8")

    assert "first.png" in output_all
    assert "second.png" in output_all
