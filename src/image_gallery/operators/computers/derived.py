from typing import cast

import pandas as pd

from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult


class TableDerivedComputer(ParameterComputer):
    """基于 parameter_table 派生尺寸参数。"""

    name = "table_derived_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"aspect_ratio", "megapixels"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产本次请求的表派生参数。"""
        requested = set(request.requested_parameters)
        produced = requested & set(self.produced_parameters)
        width = cast(pd.Series, pd.to_numeric(request.parameter_table["width"], errors="coerce"))
        height = cast(pd.Series, pd.to_numeric(request.parameter_table["height"], errors="coerce"))
        valid = cast(pd.Series, width.notna() & height.notna() & (width > 0) & (height > 0))

        updates = pd.DataFrame({"image_id": request.parameter_table["image_id"]})
        if "aspect_ratio" in produced:
            updates["aspect_ratio"] = (width / height).where(valid, pd.NA)
        if "megapixels" in produced:
            updates["megapixels"] = ((width * height) / 1_000_000).where(valid, pd.NA)

        manifest: dict[str, dict[str, object]] = {
            parameter: {
                "computer": self.name,
                "execution_mode": self.execution_mode.value,
                "config_hash": request.config_hash,
            }
            for parameter in sorted(produced)
        }
        return ParameterResult(
            parameter_updates=updates,
            relation_updates={},
            artifact_refs={},
            parameter_manifest=manifest,
        )
