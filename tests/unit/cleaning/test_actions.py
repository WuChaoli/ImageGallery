import pytest

from image_gallery.cleaning.actions import ActionFilter, normalize_actions


def test_normalize_actions_maps_clean_to_keep() -> None:
    action_filter = normalize_actions("clean", default_actions=None)

    assert action_filter == ActionFilter(stored_actions=frozenset({"keep"}), include_all=False)


def test_normalize_actions_supports_multiple_actions() -> None:
    action_filter = normalize_actions(["drop", "review"], default_actions=None)

    assert action_filter == ActionFilter(stored_actions=frozenset({"drop", "review"}), include_all=False)


def test_normalize_actions_full_is_include_all() -> None:
    action_filter = normalize_actions("full", default_actions=["drop"])

    assert action_filter == ActionFilter(stored_actions=frozenset(), include_all=True)


def test_normalize_actions_rejects_full_mixed_with_actions() -> None:
    with pytest.raises(ValueError, match="full cannot be combined"):
        normalize_actions(["full", "drop"], default_actions=None)


def test_normalize_actions_uses_defaults_when_actions_missing() -> None:
    action_filter = normalize_actions(None, default_actions=["drop", "review"])

    assert action_filter == ActionFilter(stored_actions=frozenset({"drop", "review"}), include_all=False)
