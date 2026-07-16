"""从 sample_1000 一次性生成仓库内固定的 sample_10 fixture。"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from notebooks._helpers.datasets import (
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)

SAMPLE_SIZE = 10
RANDOM_STATE = 20260706
FIXTURE_ROOT = Path(__file__).parents[1] / "tests" / "fixtures" / "sample_10"


def _safe_filename(index: int, image_id: object, image_uri: str) -> str:
    """生成稳定且可移植的本地图片文件名。"""
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "-", str(image_id)).strip(".-") or "image"
    suffix = PurePosixPath(urlparse(image_uri).path).suffix.lower()
    if not suffix or len(suffix) > 8:
        suffix = ".jpg"
    return f"{index:03d}-{safe_id}{suffix}"


def main() -> None:
    """按固定随机种子抽样、复制图片并写出相对路径 Parquet。"""
    frame = load_default_minio_sample_1000_frame().sample(n=SAMPLE_SIZE, random_state=RANDOM_STATE).copy()
    dataset = load_default_minio_sample_1000_dataset()
    image_dir = FIXTURE_ROOT / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    relative_uris: list[str] = []
    total_bytes = 0
    for index, (row_index, row) in enumerate(frame.iterrows()):
        original_uri = str(row["image_uri"])
        filename = _safe_filename(index, row["image_id"], original_uri)
        image_bytes = dataset.read_image_bytes(original_uri)
        image_path = image_dir / filename
        image_path.write_bytes(image_bytes)
        total_bytes += len(image_bytes)
        relative_uris.append((Path("images") / filename).as_posix())
        if "source_uri" not in frame.columns:
            frame.loc[row_index, "source_uri"] = original_uri

    frame["image_uri"] = relative_uris
    frame.to_parquet(FIXTURE_ROOT / "raw.parquet", index=False)
    print("image_ids=" + ",".join(str(value) for value in frame["image_id"]))
    print(f"images={len(relative_uris)} bytes={total_bytes}")


if __name__ == "__main__":
    main()
