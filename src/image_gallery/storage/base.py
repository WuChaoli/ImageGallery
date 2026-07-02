from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import overload


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
    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    def _read_bytes(self, object_path: str) -> bytes:
        raise NotImplementedError

    @overload
    def write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str: ...

    @overload
    def write_bytes(
        self, object_path: list[str], data: list[bytes], overwrite: bool = False
    ) -> list[StorageBatchResult]: ...

    def write_bytes(
        self, object_path: str | list[str], data: bytes | list[bytes], overwrite: bool = False
    ) -> str | list[StorageBatchResult]:
        """写入单个或多个 bytes；列表输入时逐项返回结果。"""
        if isinstance(object_path, str):
            if not isinstance(data, bytes):
                raise TypeError("data must be bytes when object_path is str")
            return self._write_bytes(object_path, data, overwrite)

        if not isinstance(data, list) or len(object_path) != len(data):
            return [
                StorageBatchResult(path, False, error="object_path and data must have the same length")
                for path in object_path
            ]
        return self._batch_write_bytes(zip(object_path, data, strict=True), overwrite)

    @overload
    def read_bytes(self, object_path: str) -> bytes: ...

    @overload
    def read_bytes(self, object_path: list[str]) -> list[StorageBatchResult]: ...

    def read_bytes(self, object_path: str | list[str]) -> bytes | list[StorageBatchResult]:
        """读取单个或多个 bytes；列表输入时逐项返回结果。"""
        if isinstance(object_path, str):
            return self._read_bytes(object_path)
        return self._batch_read_bytes(object_path)

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
        return self._batch_write_bytes(items, overwrite)

    def _batch_write_bytes(
        self, items: Iterable[tuple[str, bytes]], overwrite: bool = False
    ) -> list[StorageBatchResult]:
        results: list[StorageBatchResult] = []
        for object_path, data in items:
            try:
                results.append(StorageBatchResult(object_path, True, self._write_bytes(object_path, data, overwrite)))
            except Exception as exc:
                results.append(StorageBatchResult(object_path, False, error=str(exc)))
        return results

    def batch_read_bytes(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """批量读取 bytes，单个对象失败不影响其他对象。"""
        return self._batch_read_bytes(object_paths)

    def _batch_read_bytes(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        results: list[StorageBatchResult] = []
        for object_path in object_paths:
            try:
                results.append(StorageBatchResult(object_path, True, self._read_bytes(object_path)))
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
