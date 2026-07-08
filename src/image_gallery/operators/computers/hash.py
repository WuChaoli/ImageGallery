import hashlib
from functools import lru_cache

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from PIL import Image

from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult


class ImageHashComputer(ParameterComputer):
    """基于原始图片字节生产完全重复内容哈希。"""

    name = "image_hash_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"content_hash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产 content_hash。"""
        if request.image_batch is None:
            raise ValueError("ImageHashComputer requires image_batch")

        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            content_hash = hashlib.sha256(item.data).hexdigest() if item.data is not None and item.error is None else ""
            rows.append({"image_id": item.image_id, "content_hash": content_hash})

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "content_hash": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


class ImagePerceptualHashComputer(ParameterComputer):
    """基于解码图片生产视觉感知哈希。"""

    name = "image_perceptual_hash_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"phash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产 16 位十六进制 pHash。"""
        if request.image_batch is None:
            raise ValueError("ImagePerceptualHashComputer requires image_batch")

        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            phash = _compute_phash(item.image) if item.image is not None and item.error is None else ""
            rows.append({"image_id": item.image_id, "phash": phash})

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "phash": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def _compute_phash(image: Image.Image) -> str:
    """计算 64 位 DCT pHash，并编码为 16 位十六进制。"""
    grayscale = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    pixels = np.asarray(grayscale, dtype=np.float64)
    dct = _dct_matrix(32) @ pixels @ _dct_matrix(32).T
    low_freq = dct[:8, :8].copy()
    values = low_freq.flatten()
    median = float(np.median(values[1:]))
    bits = values >= median
    return _bits_to_hex(bits)


@lru_cache(maxsize=4)
def _dct_matrix(size: int) -> NDArray[np.float64]:
    """生成 DCT-II 正交变换矩阵。"""
    matrix = np.zeros((size, size), dtype=np.float64)
    factor = np.pi / (2.0 * size)
    scale0 = np.sqrt(1.0 / size)
    scale = np.sqrt(2.0 / size)
    for row in range(size):
        alpha = scale0 if row == 0 else scale
        for column in range(size):
            matrix[row, column] = alpha * np.cos((2 * column + 1) * row * factor)
    return matrix


def _bits_to_hex(bits: NDArray[np.bool_]) -> str:
    """把 64 个布尔位编码为 16 位十六进制字符串。"""
    value = 0
    for bit in bits.tolist():
        value = (value << 1) | int(bool(bit))
    return f"{value:016x}"
