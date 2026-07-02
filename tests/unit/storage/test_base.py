from image_gallery.storage.base import Storage, StorageBatchResult
from image_gallery.storage.errors import ObjectNotFoundError


class MemoryStorage(Storage):
    """用于验证 Storage 基类批量默认实现的内存 storage。"""

    storage_name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        self.objects[object_path] = data
        return self.make_image_uri(object_path)

    def _read_bytes(self, object_path: str) -> bytes:
        if object_path not in self.objects:
            raise ObjectNotFoundError(f"object not found: {object_path}")
        return self.objects[object_path]

    def exists(self, object_path: str) -> bool:
        return object_path in self.objects

    def delete(self, object_path: str) -> None:
        if object_path not in self.objects:
            raise ObjectNotFoundError(f"object not found: {object_path}")
        del self.objects[object_path]

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        self.objects[dst_object_path] = self.read_bytes(src_object_path)
        return self.make_image_uri(dst_object_path)

    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        image_uri = self.copy(src_object_path, dst_object_path, overwrite)
        self.delete(src_object_path)
        return image_uri

    def make_image_uri(self, object_path: str) -> str:
        return f"memory://{object_path}"


def test_storage_batch_write_bytes_returns_per_object_results() -> None:
    storage = MemoryStorage()

    results = storage.write_bytes(["images/a.jpg", "images/b.jpg"], [b"a", b"b"])

    assert results == [
        StorageBatchResult("images/a.jpg", True, "memory://images/a.jpg"),
        StorageBatchResult("images/b.jpg", True, "memory://images/b.jpg"),
    ]
    assert storage.objects == {"images/a.jpg": b"a", "images/b.jpg": b"b"}


def test_storage_batch_read_bytes_returns_success_and_failure_results() -> None:
    storage = MemoryStorage()
    storage.write_bytes("images/a.jpg", b"a")

    results = storage.read_bytes(["images/a.jpg", "images/missing.jpg"])

    assert results[0] == StorageBatchResult("images/a.jpg", True, b"a")
    assert results[1].object_path == "images/missing.jpg"
    assert results[1].ok is False
    assert results[1].value is None
    assert "object not found" in str(results[1].error)


def test_storage_batch_write_bytes_rejects_mismatched_data_count() -> None:
    storage = MemoryStorage()

    results = storage.write_bytes(["images/a.jpg", "images/b.jpg"], [b"a"])

    assert results[0].object_path == "images/a.jpg"
    assert results[0].ok is False
    assert "same length" in str(results[0].error)
