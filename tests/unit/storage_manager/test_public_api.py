from image_gallery.storage import Storage as LegacyStorage
from image_gallery.storage_manager import StorageManager, StoragePrefix


def test_storage_manager_is_independent_from_legacy_storage() -> None:
    assert StorageManager.__module__.startswith("image_gallery.storage_manager")
    assert StoragePrefix.__module__.startswith("image_gallery.storage_manager")
    assert not issubclass(StorageManager, LegacyStorage)


def test_storage_manager_has_no_dataset_domain_methods() -> None:
    forbidden = {"create_repo", "open_dataset", "create_branch", "create_checkpoint"}
    assert forbidden.isdisjoint(vars(StorageManager))


def test_storage_mvp_omits_alias_unbind_rotation_fallback_and_gc() -> None:
    forbidden = {
        "alias_prefix",
        "unbind_prefix",
        "rotate_credentials",
        "read_with_fallback",
        "delete_prefix",
        "delete_managed",
        "gc",
    }
    assert forbidden.isdisjoint(vars(StorageManager))
