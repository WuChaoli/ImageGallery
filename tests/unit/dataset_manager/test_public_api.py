from image_gallery.dataset import Dataset as LegacyDataset
from image_gallery.dataset_manager import Dataset, DatasetManager, DatasetRepo, DatasetView, VectorField


def test_dataset_manager_exports_new_domain_objects() -> None:
    assert DatasetManager.__module__.startswith("image_gallery.dataset_manager")
    assert DatasetRepo.__module__.startswith("image_gallery.dataset_manager")
    assert Dataset.__module__.startswith("image_gallery.dataset_manager")
    assert DatasetView.__module__.startswith("image_gallery.dataset_manager")
    assert not issubclass(Dataset, LegacyDataset)


def test_manager_does_not_expose_dataset_local_operations() -> None:
    forbidden = {"commit", "create_branch", "create_checkpoint", "scan"}
    assert forbidden.isdisjoint(vars(DatasetManager))


def test_mvp_omits_deferred_history_deletion_and_generation_apis() -> None:
    forbidden_history = {"merge", "diff", "rebase", "cherry_pick", "stash", "delete", "archive"}
    forbidden_repo = {
        "clone_from_repo",
        "delete_dataset",
        "delete_repo",
        "delete_branch",
        "delete_checkpoint",
        "gc",
        "retention",
    }
    forbidden_vector = {"generate", "model", "search", "ann", "history", "delete"}

    assert forbidden_history.isdisjoint(vars(Dataset))
    assert forbidden_repo.isdisjoint(vars(DatasetRepo))
    assert forbidden_vector.isdisjoint(vars(VectorField))
