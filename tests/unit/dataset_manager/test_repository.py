from pathlib import Path
from unittest.mock import MagicMock

import pytest

import image_gallery.dataset_manager.manager as manager_module
from image_gallery.dataset_manager import (
    DatasetManager,
    NameConflictError,
    StorageAuthorizationError,
    ValidationError,
    VectorValidationItem,
)
from image_gallery.storage_manager import StorageManager


def make_manager(tmp_path: Path) -> tuple[DatasetManager, StorageManager]:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    return manager, storage


def test_postgres_backend_migrates_before_loading_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    catalog = MagicMock()

    monkeypatch.setattr(manager_module, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(
        manager_module,
        "upgrade_control_database",
        lambda actual: events.append("migrate") if actual is engine else None,
    )

    def load_catalog(_name: str, **properties: str) -> MagicMock:
        events.append("load")
        assert properties["py-io-impl"].endswith("IsolatedFsspecFileIO")
        return catalog

    monkeypatch.setattr(manager_module, "load_catalog", load_catalog)

    created = DatasetManager.postgres(
        control_url="postgresql+psycopg://control",
        catalog_url="postgresql+psycopg://catalog",
        warehouse="file:///warehouse",
        storage_manager=StorageManager(),
    )

    assert created.catalog is catalog
    assert events == ["migrate", "load", "migrate"]

    created.close()
    engine.dispose.assert_called_once_with()
    catalog.close.assert_called_once_with()


def test_dataset_manager_context_closes_owned_resources_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    catalog = MagicMock()
    monkeypatch.setattr(manager_module.metadata, "create_all", lambda _engine: None)

    manager = DatasetManager(
        control_engine=engine,
        catalog=catalog,
        storage_manager=StorageManager(),
        owns_engine=True,
        owns_catalog=True,
    )
    with manager as entered:
        assert entered is manager
    manager.close()

    engine.dispose.assert_called_once_with()
    catalog.close.assert_called_once_with()


def test_manager_creates_and_reopens_isolated_repositories(tmp_path: Path) -> None:
    manager, _ = make_manager(tmp_path)

    first = manager.create_repo(name="Vision")
    second = manager.create_repo(name="Other")

    assert manager.open_repo(name="vision") == first
    assert manager.list_repos() == [second, first]
    assert first.repo_id != second.repo_id
    assert first.namespace != second.namespace


def test_repo_name_is_case_insensitively_unique(tmp_path: Path) -> None:
    manager, _ = make_manager(tmp_path)
    manager.create_repo(name="Vision")

    with pytest.raises(NameConflictError):
        manager.create_repo(name="vision")


def test_repo_creates_exactly_one_table_per_dataset(tmp_path: Path) -> None:
    manager, _ = make_manager(tmp_path)
    repo = manager.create_repo(name="Vision")

    dataset = repo.create_dataset(name="Raw")

    assert repo.open_dataset(name="raw") == dataset
    assert repo.list_datasets() == [dataset]
    assert dataset.table_identifier.startswith(f"{repo.namespace}.d_")
    assert manager.catalog.table_exists(dataset.table_identifier)
    assert manager.catalog.list_tables(repo.namespace) == [tuple(dataset.table_identifier.split("."))]


def test_dataset_name_is_unique_within_repo_but_not_across_repos(tmp_path: Path) -> None:
    manager, _ = make_manager(tmp_path)
    first = manager.create_repo(name="First")
    second = manager.create_repo(name="Second")
    first.create_dataset(name="Raw")
    second_dataset = second.create_dataset(name="raw")

    with pytest.raises(NameConflictError):
        first.create_dataset(name="RAW")
    assert second.open_dataset(name="RAW") == second_dataset


def test_repo_authorizes_storage_prefixes(tmp_path: Path) -> None:
    manager, storage = make_manager(tmp_path)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")

    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)

    assert repo.list_storage_prefix_ids() == [prefix.prefix_id]


def test_prefix_bindings_are_many_to_many_and_cannot_be_removed(tmp_path: Path) -> None:
    manager, storage = make_manager(tmp_path)
    first_prefix = storage.register_file_prefix(name="first", root=tmp_path / "first")
    second_prefix = storage.register_file_prefix(name="second", root=tmp_path / "second")
    first_repo = manager.create_repo(name="First")
    second_repo = manager.create_repo(name="Second")

    first_repo.bind_storage_prefix(prefix_id=first_prefix.prefix_id)
    first_repo.bind_storage_prefix(prefix_id=second_prefix.prefix_id)
    second_repo.bind_storage_prefix(prefix_id=first_prefix.prefix_id)

    assert first_repo.list_storage_prefix_ids() == sorted([first_prefix.prefix_id, second_prefix.prefix_id])
    assert second_repo.list_storage_prefix_ids() == [first_prefix.prefix_id]
    assert not hasattr(first_repo, "unbind_storage_prefix")
    assert not hasattr(first_repo, "delete_storage_prefix")


def test_dataset_rejects_unbound_prefix_before_iceberg_write(tmp_path: Path) -> None:
    manager, storage = make_manager(tmp_path)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    repo = manager.create_repo(name="Vision")
    dataset = repo.create_dataset(name="Raw")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }

    with pytest.raises(StorageAuthorizationError):
        dataset.commit(branch="main", base=dataset.open_branch(), rows=[row])

    assert dataset.open_branch().count() == 0


def test_repo_scoped_handles_reject_cross_repo_references(tmp_path: Path) -> None:
    manager, storage = make_manager(tmp_path)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    first_repo = manager.create_repo(name="First")
    second_repo = manager.create_repo(name="Second")
    first_repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    second_repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    first_dataset = first_repo.create_dataset(name="Data")
    second_dataset = second_repo.create_dataset(name="Data")
    first_tag = first_repo.create_tag(name="cat")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [first_tag.tag_id],
    }

    with pytest.raises(ValidationError):
        second_dataset.commit(branch="main", base=first_dataset.open_branch(), rows=[])
    with pytest.raises(ValidationError, match="tag_id"):
        second_dataset.commit(branch="main", base=second_dataset.open_branch(), rows=[row])

    second_field = second_repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    with pytest.raises(ValidationError):
        second_field.write(
            source=first_dataset.open_branch(),
            items={},
            validation_outputs=[(0.1, 0.2)],
        )


def test_dataset_create_is_hidden_until_recovery_finalizes(tmp_path: Path) -> None:
    storage = StorageManager()

    def fail_after_table(_operation_id: str, phase: str) -> None:
        if phase == "table_created":
            raise RuntimeError("injected finalize interruption")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_after_table,
    )
    repo = interrupted.create_repo(name="Vision")

    with pytest.raises(RuntimeError, match="injected"):
        repo.create_dataset(name="Raw")

    assert repo.list_datasets() == []
    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    assert recovered.open_repo(name="Vision").open_dataset(name="Raw").open_branch().count() == 0
    assert recovered.recover_operations() == 0
