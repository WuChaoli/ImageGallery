from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageBatchResult:
    """批量操作的逐项结果，避免单个对象失败中断整批导入。"""

    object_path: str
    ok: bool
    value: object | None = None
    error: str | None = None


class Storage(ABC):
    """单个已连接后端库的统一对象读写接口。"""

    storage_name: str

    @abstractmethod
    def write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, object_path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def exists(self, object_path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, object_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    def make_image_uri(self, object_path: str) -> str:
        raise NotImplementedError

    def batch_write_bytes(
        self, items: Iterable[tuple[str, bytes]], overwrite: bool = False
    ) -> list[StorageBatchResult]:
        """批量写入 bytes，逐项返回成功值或错误信息。"""
        results: list[StorageBatchResult] = []
        for object_path, data in items:
            try:
                results.append(StorageBatchResult(object_path, True, self.write_bytes(object_path, data, overwrite)))
            except Exception as exc:
                results.append(StorageBatchResult(object_path, False, error=str(exc)))
        return results

    def batch_read_bytes(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """批量读取 bytes，单个对象失败不影响其他对象。"""
        results: list[StorageBatchResult] = []
        for object_path in object_paths:
            try:
                results.append(StorageBatchResult(object_path, True, self.read_bytes(object_path)))
            except Exception as exc:
                results.append(StorageBatchResult(object_path, False, error=str(exc)))
        return results

    def write_many(self, items: Iterable[tuple[str, bytes]], overwrite: bool = False) -> list[StorageBatchResult]:
        """兼容旧命名；新代码优先使用 batch_write_bytes。"""
        return self.batch_write_bytes(items, overwrite)

    def read_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """兼容旧命名；新代码优先使用 batch_read_bytes。"""
        return self.batch_read_bytes(object_paths)

    def exists_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        results: list[StorageBatchResult] = []
        for object_path in object_paths:
            try:
                results.append(StorageBatchResult(object_path, True, self.exists(object_path)))
            except Exception as exc:
                results.append(StorageBatchResult(object_path, False, error=str(exc)))
        return results

    def delete_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        results: list[StorageBatchResult] = []
        for object_path in object_paths:
            try:
                self.delete(object_path)
                results.append(StorageBatchResult(object_path, True))
            except Exception as exc:
                results.append(StorageBatchResult(object_path, False, error=str(exc)))
        return results
