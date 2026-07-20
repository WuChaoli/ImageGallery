import threading
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import ConflictError, Dataset, DatasetManager
from image_gallery.storage_manager import StorageManager


def _make_dataset(tmp_path: Path) -> tuple[DatasetManager, Dataset]:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row]))
    return manager, dataset


def _inject_active_operation_after_visibility_check(
    *,
    manager: DatasetManager,
    dataset: Dataset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_load_table = manager.catalog.load_table
    injected = False

    def load_table(identifier):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        nonlocal injected
        if not injected:
            injected = True
            manager._operations.start(  # pyright: ignore[reportPrivateUsage]
                kind="commit",
                repo_id=dataset.repo_id,
                dataset_id=dataset.dataset_id,
                intent={},
            )
        return original_load_table(identifier)

    monkeypatch.setattr(manager.catalog, "load_table", load_table)


@pytest.mark.parametrize(
    "read",
    [
        pytest.param(lambda dataset: dataset.open_branch(), id="open-branch"),
        pytest.param(lambda dataset: dataset.open_checkpoint(name="saved"), id="open-checkpoint"),
        pytest.param(lambda dataset: dataset.list_checkpoints(), id="list-checkpoints"),
        pytest.param(lambda dataset: dataset.schema.list_columns(), id="schema-discovery"),
    ],
)
def test_metadata_read_rechecks_visibility_at_catalog_read_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read: Callable[[Dataset], object],
) -> None:
    manager, dataset = _make_dataset(tmp_path)
    dataset.create_checkpoint(name="saved", source=dataset.open_branch())
    _inject_active_operation_after_visibility_check(manager=manager, dataset=dataset, monkeypatch=monkeypatch)

    with pytest.raises(ConflictError, match="reconciling"):
        read(dataset)


@pytest.mark.parametrize(
    ("read", "missing_name"),
    [
        pytest.param(lambda dataset, name: dataset.open_branch(name=name), "missing-branch", id="open-branch"),
        pytest.param(
            lambda dataset, name: dataset.open_checkpoint(name=name),
            "missing-checkpoint",
            id="open-checkpoint",
        ),
    ],
)
def test_missing_ref_does_not_bypass_visibility_recheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read: Callable[[Dataset, str], object],
    missing_name: str,
) -> None:
    manager, dataset = _make_dataset(tmp_path)
    _inject_active_operation_after_visibility_check(manager=manager, dataset=dataset, monkeypatch=monkeypatch)

    with pytest.raises(ConflictError, match="reconciling"):
        read(dataset, missing_name)


class _HistoryLockProbe:
    def __init__(self) -> None:
        self.held: set[str] = set()

    @contextmanager
    def hold(self, *, dataset_id: str) -> Generator[None, None, None]:
        self.held.add(dataset_id)
        try:
            yield
        finally:
            self.held.remove(dataset_id)


@pytest.mark.parametrize("operation", ["create_dataset", "clone_dataset"])
def test_new_dataset_catalog_side_effect_holds_target_history_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    manager, source = _make_dataset(tmp_path)
    source_view = source.open_branch()
    probe = _HistoryLockProbe()
    monkeypatch.setattr(manager, "_history_lock", probe)
    monkeypatch.setattr(manager._history, "_history_lock", probe)  # pyright: ignore[reportPrivateUsage]

    target_dataset_id: str | None = None
    original_start = manager._operations.start_with_dataset_name_reservation  # pyright: ignore[reportPrivateUsage]
    original_create_table = manager.catalog.create_table

    def start_with_dataset_name_reservation(**kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        nonlocal target_dataset_id
        target_dataset_id = str(kwargs["dataset_id"])
        return original_start(**kwargs)

    def create_table(identifier, *args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        assert target_dataset_id is not None
        assert target_dataset_id in probe.held, "target Dataset history lock is not held"
        return original_create_table(identifier, *args, **kwargs)

    monkeypatch.setattr(manager._operations, "start_with_dataset_name_reservation", start_with_dataset_name_reservation)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(manager.catalog, "create_table", create_table)

    if operation == "create_dataset":
        source.open_branch().repo.create_dataset(name="Created")
    else:
        source.open_branch().repo.clone_dataset(source=source_view, name="Cloned")


@pytest.mark.parametrize("kind", ["commit", "checkpoint", "rollback", "branch"])
def test_data_or_ref_only_operation_keeps_existing_fixed_view_readable(tmp_path: Path, kind: str) -> None:
    manager, dataset = _make_dataset(tmp_path)
    fixed = dataset.open_branch()
    row = fixed.scan().iloc[0].to_dict()
    asset_id = str(row["asset_id"])
    manager._operations.start(  # pyright: ignore[reportPrivateUsage]
        kind=kind,
        repo_id=dataset.repo_id,
        dataset_id=dataset.dataset_id,
        intent={},
    )

    assert fixed.scan().iloc[0].to_dict() == row
    assert fixed.get_row(asset_id=asset_id).to_dict() == row
    assert fixed.read_image(asset_id=asset_id) == b"image"


@pytest.mark.parametrize(
    ("view_io_method", "read"),
    [
        pytest.param("scan_frame", lambda view, _asset_id: view.scan(), id="scan"),
        pytest.param("get_row_series", lambda view, asset_id: view.get_row(asset_id=asset_id), id="get-row"),
        pytest.param("read_image", lambda view, asset_id: view.read_image(asset_id=asset_id), id="read-image"),
        pytest.param("verify_image", lambda view, asset_id: view.verify_image(asset_id=asset_id), id="verify-image"),
    ],
)
def test_fixed_view_io_rechecks_schema_readability_before_returning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    view_io_method: str,
    read: Callable[[object, str], object],
) -> None:
    manager, dataset = _make_dataset(tmp_path)
    fixed = dataset.open_branch()
    asset_id = str(fixed.scan().iloc[0]["asset_id"])
    original = getattr(manager._view_io, view_io_method)  # pyright: ignore[reportPrivateUsage]
    injected = False

    def inject_schema_operation(*args, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        nonlocal injected
        result = original(*args, **kwargs)
        if not injected:
            injected = True
            manager._operations.start(  # pyright: ignore[reportPrivateUsage]
                kind="schema",
                repo_id=dataset.repo_id,
                dataset_id=dataset.dataset_id,
                intent={},
            )
        return result

    monkeypatch.setattr(manager._view_io, view_io_method, inject_schema_operation)  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(ConflictError, match="schema is reconciling"):
        read(fixed, asset_id)


def test_clone_rejects_schema_reconciling_source_without_publishing_target(tmp_path: Path) -> None:
    manager, source = _make_dataset(tmp_path)
    repo = source.open_branch().repo
    source_view = source.open_branch()
    manager._operations.start(  # pyright: ignore[reportPrivateUsage]
        kind="schema",
        repo_id=source.repo_id,
        dataset_id=source.dataset_id,
        intent={},
    )

    with pytest.raises(ConflictError, match="schema is reconciling"):
        repo.clone_dataset(source=source_view, name="Target")

    assert [dataset.name for dataset in repo.list_datasets()] == ["Raw"]


@pytest.mark.parametrize("operation", ["create_dataset", "clone_dataset"])
def test_two_managers_recover_same_new_dataset_operation_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    storage = StorageManager()
    backend_root = tmp_path / "backend"
    setup = DatasetManager.local(root=backend_root, storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = setup.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)

    if operation == "create_dataset":

        def interrupt(_operation_id: str, phase: str) -> None:
            if phase == "table_created":
                raise RuntimeError("injected create interruption")

        interrupted = DatasetManager.local(
            root=backend_root,
            storage_manager=storage,
            operation_hook=interrupt,
        )
        with pytest.raises(RuntimeError, match="create interruption"):
            interrupted.open_repo(name="Vision").create_dataset(name="Target")
        expected_rows: list[dict[str, object]] = []
        recover_method_name = "_recover_create_dataset"
    else:
        source = repo.create_dataset(name="Source")
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"clone")
        expected_rows = [
            {
                "asset_id": stored.asset_id,
                "storage_prefix_id": stored.storage_prefix_id,
                "relative_path": stored.relative_path,
                "source_uri": None,
                "tag_ids": [],
            }
        ]
        source.commit(
            branch="main",
            base=source.open_branch(),
            frame=pd.DataFrame(expected_rows),
        )

        def interrupt(_operation_id: str, phase: str) -> None:
            if phase == "clone_candidate_written":
                raise RuntimeError("injected clone interruption")

        interrupted = DatasetManager.local(
            root=backend_root,
            storage_manager=storage,
            operation_hook=interrupt,
        )
        interrupted_repo = interrupted.open_repo(name="Vision")
        interrupted_source = interrupted_repo.open_dataset(name="Source").open_branch()
        with pytest.raises(RuntimeError, match="clone interruption"):
            interrupted_repo.clone_dataset(source=interrupted_source, name="Target")
        recover_method_name = "_recover_clone"

    managers = [
        DatasetManager.local(root=backend_root, storage_manager=storage),
        DatasetManager.local(root=backend_root, storage_manager=storage),
    ]
    recover_calls = 0
    calls_guard = threading.Lock()
    for manager in managers:
        original = getattr(manager._history, recover_method_name)  # pyright: ignore[reportPrivateUsage]

        def counted_recover(*args, _original=original, **kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
            nonlocal recover_calls
            with calls_guard:
                recover_calls += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(manager._history, recover_method_name, counted_recover)  # pyright: ignore[reportPrivateUsage]

    ready = threading.Barrier(2)

    def recover(manager: DatasetManager) -> int:
        ready.wait()
        return manager.recover_operations()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(recover, managers))

    assert sorted(results) == [0, 1]
    assert recover_calls == 1
    target = managers[0].open_repo(name="Vision").open_dataset(name="Target")
    assert target.open_branch().scan().to_dict(orient="records") == expected_rows
    assert len(managers[0].catalog.load_table(target.table_identifier).snapshots()) == (0 if not expected_rows else 1)
    assert managers[0].recover_operations() == 0


@pytest.mark.parametrize("operation", ["create_dataset", "clone_dataset"])
def test_new_dataset_api_and_recovery_converge_on_one_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    storage = StorageManager()
    backend_root = tmp_path / "backend"
    api_manager = DatasetManager.local(root=backend_root, storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = api_manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"race")
    expected_rows = [
        {
            "asset_id": stored.asset_id,
            "storage_prefix_id": stored.storage_prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
        }
    ]
    source_view = source.commit(
        branch="main",
        base=source.open_branch(),
        frame=pd.DataFrame(expected_rows),
    ).view
    recovery_manager = DatasetManager.local(root=backend_root, storage_manager=storage)

    reservation_created = threading.Event()
    allow_api_to_continue = threading.Event()
    original_start = api_manager._operations.start_with_dataset_name_reservation  # pyright: ignore[reportPrivateUsage]

    def pause_after_reservation(**kwargs):  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        operation_id = original_start(**kwargs)
        reservation_created.set()
        assert allow_api_to_continue.wait(timeout=10)
        return operation_id

    monkeypatch.setattr(
        api_manager._operations,  # pyright: ignore[reportPrivateUsage]
        "start_with_dataset_name_reservation",
        pause_after_reservation,
    )

    def invoke_api() -> Dataset:
        if operation == "create_dataset":
            return repo.create_dataset(name="Target")
        return repo.clone_dataset(source=source_view, name="Target")

    with ThreadPoolExecutor(max_workers=1) as executor:
        api_result = executor.submit(invoke_api)
        assert reservation_created.wait(timeout=10)
        assert recovery_manager.recover_operations() == 1
        allow_api_to_continue.set()
        returned = api_result.result(timeout=10)

    reopened = recovery_manager.open_repo(name="Vision").open_dataset(name="Target")
    assert returned.dataset_id == reopened.dataset_id
    visible_rows = [] if operation == "create_dataset" else expected_rows
    assert reopened.open_branch().scan().to_dict(orient="records") == visible_rows
    assert len(recovery_manager.catalog.load_table(reopened.table_identifier).snapshots()) == (
        0 if operation == "create_dataset" else 1
    )
    assert recovery_manager.recover_operations() == 0
