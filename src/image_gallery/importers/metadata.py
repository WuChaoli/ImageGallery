import hashlib
from pathlib import Path
from typing import Any

from PIL import Image


def extract_basic_metadata(path: str | Path) -> dict[str, Any]:
    """抽取导入阶段 raw Dataset 需要的低成本基础事实。"""
    image_path = Path(path)
    data = image_path.read_bytes()
    checksum = "sha256:" + hashlib.sha256(data).hexdigest()
    with Image.open(image_path) as image:
        bands = image.getbands()
        return {
            "file_size_bytes": len(data),
            "checksum": checksum,
            "image_format": image.format or image_path.suffix.lstrip(".").upper(),
            "width": image.width,
            "height": image.height,
            "channels": len(bands),
            "color_mode": image.mode,
        }
