from typing import Literal

from image_gallery.cleaning.tables import CleaningTables
from image_gallery.dataset import Dataset

ReviewPolicy = Literal["keep", "strict"]


def export_cleaning_result(
    kind: str,
    tables: CleaningTables,
    output_path: str,
    *,
    review_policy: ReviewPolicy = "keep",
) -> Dataset:
    """按 kind 导出清洗结果，并返回 Dataset。"""
    if review_policy not in {"keep", "strict"}:
        raise ValueError(f"unsupported review_policy: {review_policy}")
    normalized_kind = kind.strip().lower()
    if normalized_kind in {"parameters", "parameter"}:
        frame = tables.parameter_table
    elif normalized_kind in {"evaluations", "evaluation", "full"}:
        frame = tables.evaluation_table.copy()
        if review_policy == "strict":
            frame = frame.copy()
            frame.loc[frame["final_action"] == "review", "final_action"] = "drop"
    elif normalized_kind in {"clean", "kept"}:
        if review_policy == "keep":
            frame = tables.evaluation_table[tables.evaluation_table["final_action"].isin(["keep", "review"])]
        else:
            frame = tables.evaluation_table[tables.evaluation_table["final_action"] == "keep"]
    elif normalized_kind == "review":
        frame = tables.evaluation_table[tables.evaluation_table["final_action"] == "review"].copy()
        if review_policy == "strict":
            frame = frame.iloc[0:0].copy()
    elif normalized_kind in {"dropped", "drops"}:
        if review_policy == "strict":
            frame = tables.evaluation_table[
                tables.evaluation_table["final_action"].isin(["drop", "review"])
            ].copy()
        else:
            frame = tables.evaluation_table[tables.evaluation_table["final_action"] == "drop"].copy()
    else:
        raise ValueError(f"unsupported export kind: {kind}")
    return Dataset.write(frame.copy(), output_path)
