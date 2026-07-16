from typing import cast

import pandas as pd

from image_gallery.cleaning.tables import CleaningTables
from image_gallery.dataset import Dataset


def export_cleaning_result(
    kind: str,
    tables: CleaningTables,
    output_path: str,
) -> Dataset:
    """按 kind 导出清洗结果，并返回 Dataset。"""
    if kind in {"parameters", "parameter"}:
        frame = tables.parameter_table
    elif kind in {"evaluations", "evaluation"} or kind == "full":
        frame = tables.evaluation_table
    elif kind == "clean":
        frame = cast(pd.DataFrame, tables.evaluation_table[tables.evaluation_table["final_action"] == "keep"])
    elif kind == "review":
        frame = cast(pd.DataFrame, tables.evaluation_table[tables.evaluation_table["final_action"] == "review"])
    elif kind == "dropped":
        frame = cast(pd.DataFrame, tables.evaluation_table[tables.evaluation_table["final_action"] == "drop"])
    else:
        raise ValueError(f"unsupported export kind: {kind}")
    return Dataset.write(frame.copy(), output_path)
