import pandas as pd

from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class ImageMetadataComputer(ParameterComputer):
    """基于 Cleaner 共享 ImageBatch 生产解码和尺寸参数。"""

    name = "image_metadata_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset(
        {
            "width",
            "height",
            "format",
            "decode_ok",
            "decode_error",
            "file_size",
        }
    )

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """从共享 ImageBatch 中提取被请求的元数据参数。"""
        if request.image_batch is None:
            raise ValueError("ImageMetadataComputer requires image_batch")

        requested = set(request.requested_parameters)
        produced = requested & set(self.produced_parameters)
        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            values = self._values_for_item(item)
            row: dict[str, object] = {"image_id": item.image_id}
            for parameter in sorted(produced):
                row[parameter] = values[parameter]
            rows.append(row)

        manifest: dict[str, dict[str, object]] = {
            parameter: {
                "computer": self.name,
                "stage": self.stage.value,
                "config_hash": request.config_hash,
            }
            for parameter in sorted(produced)
        }
        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest=manifest,
        )

    def _values_for_item(self, item: ImageBatchItem) -> dict[str, object]:
        """把单张共享图片上下文转换为元数据字段。"""
        if item.error or item.image is None:
            return {
                "width": pd.NA,
                "height": pd.NA,
                "format": "",
                "decode_ok": False,
                "decode_error": str(item.error or "image decode failed"),
                "file_size": len(item.data) if item.data is not None else pd.NA,
            }
        return {
            "width": int(item.image.width),
            "height": int(item.image.height),
            "format": str(getattr(item.image, "format", "") or ""),
            "decode_ok": True,
            "decode_error": "",
            "file_size": len(item.data) if item.data is not None else pd.NA,
        }
