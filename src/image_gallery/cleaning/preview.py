from dataclasses import dataclass

import pandas as pd

ACTION_PRIORITY = {"keep": 0, "review": 1, "drop": 2, "restricted": 3}


@dataclass(frozen=True)
class PreviewResult:
    """清洗预览结果。"""

    total_count: int
    clean_count: int
    review_count: int
    dropped_count: int
    restricted_count: int
    operator_summary: pd.DataFrame
    sample_rows: pd.DataFrame


def build_preview(
    evaluation_table: pd.DataFrame,
    operator_outputs: dict[str, list[str]],
    limit: int = 20,
) -> PreviewResult:
    """基于 evaluation_table 构造预览摘要。"""
    evaluated = apply_final_action(evaluation_table, operator_outputs)
    return PreviewResult(
        total_count=len(evaluated),
        clean_count=_count_action(evaluated, "keep"),
        review_count=_count_action(evaluated, "review"),
        dropped_count=_count_action(evaluated, "drop"),
        restricted_count=_count_action(evaluated, "restricted"),
        operator_summary=_build_operator_summary(evaluated, operator_outputs),
        sample_rows=evaluated.head(limit).copy(),
    )


def apply_final_action(
    evaluation_table: pd.DataFrame,
    operator_outputs: dict[str, list[str]],
) -> pd.DataFrame:
    """根据各算子的 action 列生成 final_action、final_reason 和 triggered_operator_names。"""
    result = evaluation_table.copy()
    final_actions: list[str] = []
    final_reasons: list[str] = []
    triggered_operator_names: list[str] = []

    action_specs = _action_specs(operator_outputs)
    for _, row in result.iterrows():
        row_hits: list[tuple[str, str, str]] = []
        for operator_name, action_column, reason_column in action_specs:
            action = _normalize_action(row.get(action_column))
            if action == "keep":
                continue
            reason = str(row.get(reason_column, "") or "")
            row_hits.append((operator_name, action, reason))

        if not row_hits:
            final_actions.append("keep")
            final_reasons.append("")
            triggered_operator_names.append("")
            continue

        row_hits = sorted(row_hits, key=lambda hit: ACTION_PRIORITY[hit[1]], reverse=True)
        selected_action = row_hits[0][1]
        final_actions.append(selected_action)
        final_reasons.append("; ".join(reason for _, _, reason in row_hits if reason))
        triggered_operator_names.append(";".join(operator_name for operator_name, _, _ in row_hits))

    result["final_action"] = final_actions
    result["final_reason"] = final_reasons
    result["triggered_operator_names"] = triggered_operator_names
    return result


def _count_action(evaluation_table: pd.DataFrame, action: str) -> int:
    """统计 final_action 的数量。"""
    return int((evaluation_table["final_action"] == action).sum())


def _build_operator_summary(
    evaluation_table: pd.DataFrame,
    operator_outputs: dict[str, list[str]],
) -> pd.DataFrame:
    """按算子 action 列生成命中摘要。"""
    rows: list[dict[str, object]] = []
    for operator_name, action_column, _ in _action_specs(operator_outputs):
        counts = evaluation_table[action_column].fillna("").map(_normalize_action).value_counts()
        rows.append(
            {
                "operator_name": operator_name,
                "keep": int(counts.get("keep", 0)),
                "review": int(counts.get("review", 0)),
                "drop": int(counts.get("drop", 0)),
                "restricted": int(counts.get("restricted", 0)),
            }
        )
    return pd.DataFrame(rows, columns=["operator_name", "keep", "review", "drop", "restricted"])


def _action_specs(operator_outputs: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """从 operator_outputs 中识别 action/reason 列。"""
    specs: list[tuple[str, str, str]] = []
    for operator_name, columns in operator_outputs.items():
        action_columns = [column for column in columns if column.endswith("_action")]
        for action_column in action_columns:
            reason_column = action_column.removesuffix("_action") + "_reason"
            specs.append((operator_name, action_column, reason_column))
    return specs


def _normalize_action(value: object) -> str:
    """把空值和未知 action 归一为 keep。"""
    action = str(value or "").strip()
    if action in ACTION_PRIORITY:
        return action
    return "keep"
