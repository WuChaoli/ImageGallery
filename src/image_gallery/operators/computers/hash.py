import hashlib

import pandas as pd

from image_gallery.operators.computers.base import ComputeStage, ParameterComputer, ParameterRequest, ParameterResult


class ImageHashComputer(ParameterComputer):
    """基于原始图片字节生产完全重复内容哈希。"""

    name = "image_hash_computer"
    stage = ComputeStage.IMAGE_BATCH
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
                    "stage": self.stage.value,
                    "config_hash": request.config_hash,
                }
            },
        )
