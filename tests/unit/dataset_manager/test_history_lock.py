import hashlib
import importlib
import importlib.util
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine


def _history_lock_type():  # pyright: ignore[reportUnknownParameterType]
    spec = importlib.util.find_spec("image_gallery.dataset_manager._history_lock")
    assert spec is not None
    module = importlib.import_module("image_gallery.dataset_manager._history_lock")
    return module.DatasetHistoryLock


def test_local_history_lock_is_shared_by_backend_identity(tmp_path: Path) -> None:
    history_lock_type = _history_lock_type()
    database_url = f"sqlite:///{(tmp_path / 'control.db').as_posix()}"
    first_engine = create_engine(database_url)
    second_engine = create_engine(database_url)
    first = history_lock_type(first_engine)
    second = history_lock_type(second_engine)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def hold_first() -> None:
        with first.hold(dataset_id="dataset-1"):
            first_entered.set()
            assert release_first.wait(timeout=2)

    def hold_second() -> None:
        assert first_entered.wait(timeout=2)
        with second.hold(dataset_id="dataset-1"):
            second_entered.set()

    first_thread = threading.Thread(target=hold_first)
    second_thread = threading.Thread(target=hold_second)
    first_thread.start()
    second_thread.start()
    try:
        assert first_entered.wait(timeout=2)
        assert not second_entered.wait(timeout=0.1)
        release_first.set()
        assert second_entered.wait(timeout=2)
    finally:
        release_first.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)
        first_engine.dispose()
        second_engine.dispose()


def test_local_history_lock_keeps_datasets_independent(tmp_path: Path) -> None:
    history_lock_type = _history_lock_type()
    engine = create_engine(f"sqlite:///{(tmp_path / 'control.db').as_posix()}")
    first = history_lock_type(engine)
    second = history_lock_type(engine)
    other_entered = threading.Event()

    def hold_other_dataset() -> None:
        with second.hold(dataset_id="dataset-2"):
            other_entered.set()

    try:
        with first.hold(dataset_id="dataset-1"):
            thread = threading.Thread(target=hold_other_dataset)
            thread.start()
            assert other_entered.wait(timeout=2)
            thread.join(timeout=2)
    finally:
        engine.dispose()


def test_postgres_history_lock_preserves_key_and_releases_connection_on_failure() -> None:
    history_lock_type = _history_lock_type()
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = MagicMock()
    engine.connect.return_value = connection
    dataset_id = "dataset-a"
    expected_digest = hashlib.sha256(f"image-gallery-dataset-history:{dataset_id}".encode()).digest()
    expected_key = int.from_bytes(expected_digest[:8], byteorder="big", signed=True)

    with pytest.raises(RuntimeError, match="injected"):
        with history_lock_type(engine).hold(dataset_id=dataset_id):
            raise RuntimeError("injected")

    engine.connect.assert_called_once_with()
    assert len(connection.execute.call_args_list) == 2
    lock_call, unlock_call = connection.execute.call_args_list
    assert "pg_advisory_lock" in str(lock_call.args[0])
    assert "pg_advisory_unlock" in str(unlock_call.args[0])
    assert lock_call.args[1] == {"lock_key": expected_key}
    assert unlock_call.args[1] == {"lock_key": expected_key}
    connection.close.assert_called_once_with()
