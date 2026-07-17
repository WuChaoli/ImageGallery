"""从现有 sample_1000 一次性制备可离线使用的演示图片。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from notebooks._helpers.datasets import load_default_minio_sample_1000_dataset, load_default_minio_sample_1000_frame

SAMPLE_SEED = 20260717
SAMPLE_SIZE = 20


def select_sample_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """以固定随机种子从 1000 行来源中无放回抽取 20 行。"""
    if len(frame) != 1000 or "image_uri" not in frame:
        raise ValueError("sample_1000 必须包含 1000 行和 image_uri 列")
    return frame.sample(n=SAMPLE_SIZE, replace=False, random_state=SAMPLE_SEED).reset_index(drop=True)


def prepare_materials(output_root: str | Path) -> Path:
    """下载固定样本并写入图片目录与来源 manifest。"""
    root = Path(output_root)
    image_dir = root / "raw_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    frame = load_default_minio_sample_1000_frame()
    dataset = load_default_minio_sample_1000_dataset()
    items: list[dict[str, object]] = []
    for index, row in select_sample_rows(frame).iterrows():
        uri = str(row["image_uri"])
        data = dataset.read_image_bytes(uri)
        digest = hashlib.sha256(data).hexdigest()
        suffix = Path(urlparse(uri).path).suffix.lower() or ".jpg"
        filename = f"sample-{index:02d}-{digest[:12]}{suffix}"
        relative_path = Path("raw_images") / filename
        (root / relative_path).write_bytes(data)
        items.append(
            {
                "source_image_uri": uri,
                "local_path": relative_path.as_posix(),
                "sha256": digest,
                "size_bytes": len(data),
            }
        )
    manifest_path = root / "sample_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "seed": SAMPLE_SEED,
                "source_row_count": len(frame),
                "sample_size": SAMPLE_SIZE,
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


if __name__ == "__main__":
    prepare_materials(Path(__file__).parent / "materials")
