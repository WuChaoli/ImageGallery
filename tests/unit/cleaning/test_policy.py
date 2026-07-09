from image_gallery.cleaning.policy import BatchPolicy, NodePolicy


def test_node_policy_merge_uses_override_values() -> None:
    base = NodePolicy(batch=BatchPolicy(size=128))
    override = NodePolicy(batch=BatchPolicy(size=32))

    merged = NodePolicy.merge(base, override)

    assert merged.batch.size == 32


def test_node_policy_preset_balanced_has_checkpoint_enabled() -> None:
    policy = NodePolicy.preset("balanced")

    assert policy.checkpoint.enabled is True
    assert policy.cache.scope == "system"
