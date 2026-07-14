from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class OperatorPreviewCase:
    """单个轻量质量算子的 HTML 预览生成配置。"""

    operator_name: str
    config: dict[str, object]
    action_column: str
    caption_columns: list[str]


OPERATOR_PREVIEW_CASES = [
    OperatorPreviewCase(
        operator_name="exposure",
        config={},
        action_column="exposure_action",
        caption_columns=[
            "image_id",
            "final_action",
            "dark_pixel_ratio",
            "bright_pixel_ratio",
            "clipped_pixel_ratio",
            "exposure_action",
            "exposure_reason",
        ],
    ),
    OperatorPreviewCase(
        operator_name="border_padding",
        config={},
        action_column="border_padding_action",
        caption_columns=[
            "image_id",
            "final_action",
            "border_padding_ratio",
            "border_padding_sides",
            "border_padding_color",
            "border_padding_action",
            "border_padding_reason",
        ],
    ),
    OperatorPreviewCase(
        operator_name="noise",
        config={"max_score": 0.01},
        action_column="noise_action",
        caption_columns=["image_id", "final_action", "noise_score", "noise_action", "noise_reason"],
    ),
    OperatorPreviewCase(
        operator_name="mono_color",
        config={},
        action_column="mono_color_action",
        caption_columns=["image_id", "final_action", "mono_color_score", "mono_color_action", "mono_color_reason"],
    ),
    OperatorPreviewCase(
        operator_name="animated",
        config={},
        action_column="animated_action",
        caption_columns=["image_id", "final_action", "frame_count", "animated", "animated_action", "animated_reason"],
    ),
    OperatorPreviewCase(
        operator_name="orientation",
        config={},
        action_column="orientation_action",
        caption_columns=[
            "image_id",
            "final_action",
            "exif_orientation",
            "orientation_risk",
            "orientation_action",
            "orientation_reason",
        ],
    ),
]


def generate_previews(output_root: Path) -> dict[str, Path]:
    """为每个第二批轻量质量算子生成独立 HTML 预览页。"""
    output_root.mkdir(parents=True, exist_ok=True)
    preview_paths: dict[str, Path] = {}
    for case in OPERATOR_PREVIEW_CASES:
        case_dir = output_root / _operator_slug(case.operator_name)
        case_dir.mkdir(parents=True, exist_ok=True)
        dataset = _write_case_dataset(case.operator_name, case_dir)
        cleaner = BasicCleaner([{case.operator_name: case.config}])
        result = cleaner.run(dataset, output_dir=case_dir / "cleaning")
        preview_paths[case.operator_name] = result.preview_html(
            str(case_dir / "preview.html"),
            action="review",
            caption_columns=case.caption_columns,
        )
    return preview_paths


def _write_case_dataset(operator_name: str, case_dir: Path) -> Dataset:
    """写出单算子的触发样本和对照样本数据集。"""
    images_dir = case_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    trigger_path = _write_trigger_image(operator_name, images_dir)
    control_path = images_dir / "control.png"
    _write_control_image(control_path)
    frame = pd.DataFrame(
        {
            "image_id": ["trigger", "control"],
            "image_uri": [str(trigger_path), str(control_path)],
        }
    )
    return Dataset.write(frame, str(case_dir / "raw.parquet"))


def _write_trigger_image(operator_name: str, images_dir: Path) -> Path:
    """根据算子类型写出稳定触发样本。"""
    if operator_name == "exposure":
        path = images_dir / "trigger_dark.png"
        Image.new("RGB", (32, 32), color=(0, 0, 0)).save(path)
        return path
    if operator_name == "border_padding":
        path = images_dir / "trigger_border.png"
        image = Image.new("RGB", (32, 32), color=(255, 255, 255))
        for x in range(10, 22):
            for y in range(10, 22):
                image.putpixel((x, y), (30, 80, 130))
        image.save(path)
        return path
    if operator_name == "noise":
        path = images_dir / "trigger_noise.png"
        image = Image.new("RGB", (32, 32), color=(0, 0, 0))
        for x in range(32):
            for y in range(32):
                if (x + y) % 2 == 0:
                    image.putpixel((x, y), (255, 255, 255))
        image.save(path)
        return path
    if operator_name == "mono_color":
        path = images_dir / "trigger_mono.png"
        Image.new("RGB", (32, 32), color=(18, 90, 170)).save(path)
        return path
    if operator_name == "animated":
        path = images_dir / "trigger_animated.gif"
        frames = [
            Image.new("RGB", (32, 32), color=(200, 40, 40)),
            Image.new("RGB", (32, 32), color=(40, 120, 220)),
        ]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)
        return path
    if operator_name == "orientation":
        path = images_dir / "trigger_orientation.jpg"
        image = Image.new("RGB", (32, 48), color=(100, 120, 140))
        exif = image.getexif()
        exif[274] = 6
        image.save(path, exif=exif)
        return path
    raise ValueError(f"unsupported operator preview case: {operator_name}")


def _write_control_image(path: Path) -> None:
    """写出不触发第二批轻量质量算子的对照图。"""
    image = Image.new("RGB", (32, 32), color=(90, 120, 150))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (110 + x % 8, 130 + y % 8, 150))
    image.save(path)


def _operator_slug(operator_name: str) -> str:
    """把算子名转换为适合目录名的 slug。"""
    return operator_name.replace(".", "_")


def main() -> None:
    """生成默认测试目录下的每算子 HTML 页面。"""
    output_root = Path("datasets/tests/operators_light_quality")
    preview_paths = generate_previews(output_root)
    for operator_name, path in preview_paths.items():
        print(f"{operator_name}: {path}")


if __name__ == "__main__":
    main()
