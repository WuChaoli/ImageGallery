from collections.abc import Iterable
from dataclasses import dataclass

_USER_TO_STORED_ACTION = {
    "clean": "keep",
    "keep": "keep",
    "drop": "drop",
    "review": "review",
}


@dataclass(frozen=True)
class ActionFilter:
    """用户 action 筛选归一化后的存储层表达。"""

    stored_actions: frozenset[str]
    include_all: bool = False


def normalize_actions(
    actions: str | Iterable[str] | None,
    default_actions: list[str] | None,
) -> ActionFilter:
    """把用户传入的 actions 归一化为存储层 keep/drop/review。"""
    selected = default_actions if actions is None else actions
    if selected is None:
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    if isinstance(selected, str):
        values = [selected]
    else:
        values = list(selected)
    normalized_values = [str(value).strip().lower() for value in values]
    if not normalized_values:
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    if "full" in normalized_values:
        if len(normalized_values) != 1:
            raise ValueError("full cannot be combined with other actions")
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    unknown = [value for value in normalized_values if value not in _USER_TO_STORED_ACTION]
    if unknown:
        raise ValueError(f"unknown actions: {unknown}")
    return ActionFilter(
        stored_actions=frozenset(_USER_TO_STORED_ACTION[value] for value in normalized_values),
        include_all=False,
    )
