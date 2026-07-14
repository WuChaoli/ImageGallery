import tempfile
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.run_store import DiskRunStore, MemoryRunStore, RunStore, TemporaryRunStore


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame({"image_id": ["img_0", "img_1"], "score": [0.5, 0.8]})


class TestRunStoreProtocol:
    def test_memory_is_run_store(self) -> None:
        assert isinstance(MemoryRunStore(), RunStore)

    def test_temporary_is_run_store(self) -> None:
        store = TemporaryRunStore()
        assert isinstance(store, RunStore)
        store.cleanup()

    def test_disk_is_run_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            assert isinstance(store, RunStore)
            store.cleanup()


class TestMemoryRunStore:
    def test_write_and_read_table(self) -> None:
        store = MemoryRunStore()
        frame = _sample_frame()
        path = store.write_table("test", frame)
        assert "memory" in str(path)
        result = store.read_table("test")
        pd.testing.assert_frame_equal(result, frame)

    def test_read_missing_table_raises(self) -> None:
        store = MemoryRunStore()
        with pytest.raises(KeyError, match="not found"):
            store.read_table("missing")

    def test_write_and_read_json(self) -> None:
        store = MemoryRunStore()
        data = {"key": "value", "count": 42}
        path = store.write_json("config", data)
        assert "memory" in str(path)
        result = store.read_json("config")
        assert result == data

    def test_read_missing_json_raises(self) -> None:
        store = MemoryRunStore()
        with pytest.raises(KeyError, match="not found"):
            store.read_json("missing")

    def test_materialize_dataset(self) -> None:
        store = MemoryRunStore()
        frame = _sample_frame()
        path = store.materialize_dataset(frame)
        assert "memory" in str(path)

    def test_cleanup_clears_data(self) -> None:
        store = MemoryRunStore()
        store.write_table("test", _sample_frame())
        store.write_json("config", {"key": "value"})
        store.cleanup()
        with pytest.raises(KeyError):
            store.read_table("test")
        with pytest.raises(KeyError):
            store.read_json("config")


class TestTemporaryRunStore:
    def test_write_and_read_table(self) -> None:
        store = TemporaryRunStore()
        try:
            frame = _sample_frame()
            path = store.write_table("test", frame)
            assert path.exists()
            result = store.read_table("test")
            pd.testing.assert_frame_equal(result, frame)
        finally:
            store.cleanup()

    def test_write_and_read_json(self) -> None:
        store = TemporaryRunStore()
        try:
            data = {"key": "value"}
            path = store.write_json("config", data)
            assert path.exists()
            result = store.read_json("config")
            assert result == data
        finally:
            store.cleanup()

    def test_cleanup_removes_directory(self) -> None:
        store = TemporaryRunStore()
        tmp_dir = store.run_dir()
        store.write_table("test", _sample_frame())
        assert tmp_dir.exists()
        store.cleanup()
        assert not tmp_dir.exists()

    def test_read_missing_table_raises(self) -> None:
        store = TemporaryRunStore()
        try:
            with pytest.raises(FileNotFoundError):
                store.read_table("missing")
        finally:
            store.cleanup()

    def test_read_missing_json_raises(self) -> None:
        store = TemporaryRunStore()
        try:
            with pytest.raises(FileNotFoundError):
                store.read_json("missing")
        finally:
            store.cleanup()

    def test_materialize_dataset(self) -> None:
        store = TemporaryRunStore()
        try:
            frame = _sample_frame()
            path = store.materialize_dataset(frame)
            assert path.exists()
            result = pd.read_parquet(path)
            pd.testing.assert_frame_equal(result, frame)
        finally:
            store.cleanup()


class TestDiskRunStore:
    def test_write_and_read_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            frame = _sample_frame()
            path = store.write_table("test", frame)
            assert path.exists()
            result = store.read_table("test")
            pd.testing.assert_frame_equal(result, frame)
            store.cleanup()

    def test_write_and_read_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            data = {"key": "value"}
            path = store.write_json("config", data)
            assert path.exists()
            result = store.read_json("config")
            assert result == data
            store.cleanup()

    def test_run_dir_is_cache_root_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "my-run")
            expected = Path(tmp) / "my-run"
            assert store.run_dir() == expected
            store.cleanup()

    def test_cleanup_removes_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            store.write_table("test", _sample_frame())
            run_dir = store.run_dir()
            assert run_dir.exists()
            store.cleanup()
            assert not run_dir.exists()

    def test_materialize_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            frame = _sample_frame()
            path = store.materialize_dataset(frame)
            assert path.exists()
            result = pd.read_parquet(path)
            pd.testing.assert_frame_equal(result, frame)
            store.cleanup()

    def test_read_missing_table_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            with pytest.raises(FileNotFoundError):
                store.read_table("missing")
            store.cleanup()

    def test_read_missing_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiskRunStore(tmp, "run-1")
            with pytest.raises(FileNotFoundError):
                store.read_json("missing")
            store.cleanup()
