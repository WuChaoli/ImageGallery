from dataclasses import dataclass

from image_gallery.cleaning.actions import ActionFilter, normalize_actions


@dataclass(frozen=True)
class PreviewPolicy:
    """预览策略，用于描述每个算子默认的预览呈现与排序行为。"""

    default_actions: list[str] | None = None
    caption_columns: list[str] | None = None
    groupby: str | None = None
    include_group_context: bool = False
    sort_by: list[str] | None = None
    ascending: bool | list[bool] = True
    max_rows: int = 200
    max_groups: int = 50
    max_items_per_group: int = 20
    thumbnail_size: int = 320
    columns_per_row: int = 6


@dataclass(frozen=True)
class ResolvedPreviewOptions:
    """解析后的预览选项，全部字段均为最终运行值。"""

    actions: list[str]
    include_all_actions: bool
    caption_columns: list[str]
    groupby: str | None
    include_group_context: bool
    sort_by: list[str]
    ascending: bool | list[bool]
    max_rows: int
    max_groups: int
    max_items_per_group: int
    thumbnail_size: int
    columns_per_row: int


def resolve_preview_policy(
    policy: PreviewPolicy,
    actions: list[str] | str | None,
    caption_columns: list[str] | None,
    groupby: str | None,
    include_group_context: bool | None,
    sort_by: list[str] | None,
    ascending: bool | list[bool] | None,
) -> ResolvedPreviewOptions:
    """把策略与用户覆盖参数合并为最终预览配置。"""
    action_filter: ActionFilter = normalize_actions(actions, policy.default_actions)
    resolved_actions = (
        []
        if action_filter.include_all
        else sorted(action_filter.stored_actions)
    )

    resolved_caption_columns = list(caption_columns or policy.caption_columns or [])
    resolved_sort_by = list(sort_by or policy.sort_by or [])

    return ResolvedPreviewOptions(
        actions=resolved_actions,
        include_all_actions=action_filter.include_all,
        caption_columns=resolved_caption_columns,
        groupby=groupby,
        include_group_context=policy.include_group_context if include_group_context is None else include_group_context,
        sort_by=resolved_sort_by,
        ascending=policy.ascending if ascending is None else ascending,
        max_rows=policy.max_rows,
        max_groups=policy.max_groups,
        max_items_per_group=policy.max_items_per_group,
        thumbnail_size=policy.thumbnail_size,
        columns_per_row=policy.columns_per_row,
    )
