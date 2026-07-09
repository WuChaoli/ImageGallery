from image_gallery.cleaning.preview_policy import PreviewPolicy, resolve_preview_policy


def test_resolve_preview_policy_keeps_explicit_overrides() -> None:
    policy = PreviewPolicy(
        default_actions=["drop"],
        caption_columns=["blur_score"],
        groupby=None,
        include_group_context=False,
        sort_by=["blur_score"],
        ascending=True,
    )

    resolved = resolve_preview_policy(
        policy,
        actions=["review"],
        caption_columns=None,
        groupby="custom_group",
        include_group_context=None,
        sort_by=None,
        ascending=None,
    )

    assert resolved.actions == ["review"]
    assert resolved.caption_columns == ["blur_score"]
    assert resolved.groupby == "custom_group"
    assert resolved.sort_by == ["blur_score"]
