from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar, overload

_BatchItem = TypeVar("_BatchItem")


@dataclass(frozen=True)
class StorageBatchResult:
    """批量操作的逐项结果，避免单个对象失败中断整批导入。"""

    object_path: str
    ok: bool
    value: object | None = None
    error: str | None = None


def _collect_batch_results(
    items: Iterable[_BatchItem],
    *,
    object_path: Callable[[_BatchItem], str],
    operation: Callable[[_BatchItem], object],
) -> list[StorageBatchResult]:
    """按输入顺序执行批量操作，并隔离单项异常。"""
    results: list[StorageBatchResult] = []
    for item in items:
        path = object_path(item)
        try:
            results.append(StorageBatchResult(path, True, operation(item)))
        # 批量 Storage API 必须隔离单个对象失败并返回结构化结果。
        except Exception as exc:  # noqa: BLE001
            results.append(StorageBatchResult(path, False, error=str(exc)))
    return results


class Storage(ABC):
    """单个已连接后端库的统一对象读写接口。"""

    storage_name: str

    @abstractmethod
    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        """写入单个对象并返回可持久化的 image_uri。"""
        raise NotImplementedError

    @abstractmethod
    def _read_bytes(self, object_path: str) -> bytes:
        """读取单个对象的原始 bytes。"""
        raise NotImplementedError

    @overload
    def write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        """写入单个对象并返回 image_uri。"""
        ...

    @overload
    def write_bytes(
        self, object_path: list[str], data: list[bytes], overwrite: bool = False
    ) -> list[StorageBatchResult]:
        """批量写入对象，逐项返回成功值或错误信息。"""
        ...

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
    def read_bytes(self, object_path: str) -> bytes:
        """读取单个对象的 bytes。"""
        ...

    @overload
    def read_bytes(self, object_path: list[str]) -> list[StorageBatchResult]:
        """批量读取对象，逐项返回 bytes 或错误信息。"""
        ...

    def read_bytes(self, object_path: str | list[str]) -> bytes | list[StorageBatchResult]:
        """读取单个或多个 bytes；列表输入时逐项返回结果。"""
        if isinstance(object_path, str):
            return self._read_bytes(object_path)
        return self._batch_read_bytes(object_path)

    @abstractmethod
    def exists(self, object_path: str) -> bool:
        """检查对象是否存在。"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, object_path: str) -> None:
        """删除对象，不存在时由具体后端决定是否抛出 ObjectNotFoundError。"""
        raise NotImplementedError

    @abstractmethod
    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """复制对象并返回目标对象的 image_uri。"""
        raise NotImplementedError

    @abstractmethod
    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """移动对象并返回目标对象的 image_uri。"""
        raise NotImplementedError

    @abstractmethod
    def make_image_uri(self, object_path: str) -> str:
        """把后端内部 object_path 转换为数据集可持久化的 image_uri。"""
        raise NotImplementedError

    def batch_write_bytes(
        self, items: Iterable[tuple[str, bytes]], overwrite: bool = False
    ) -> list[StorageBatchResult]:
        """批量写入 bytes，逐项返回成功值或错误信息。"""
        return self._batch_write_bytes(items, overwrite)

    def _batch_write_bytes(
        self, items: Iterable[tuple[str, bytes]], overwrite: bool = False
    ) -> list[StorageBatchResult]:
        """逐项写入对象，并把单项异常转换为批量结果。"""
        return _collect_batch_results(
            items,
            object_path=lambda item: item[0],
            operation=lambda item: self._write_bytes(item[0], item[1], overwrite),
        )

    def batch_read_bytes(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """批量读取 bytes，单个对象失败不影响其他对象。"""
        return self._batch_read_bytes(object_paths)

    def _batch_read_bytes(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """逐项读取对象，并把单项异常转换为批量结果。"""
        return _collect_batch_results(
            object_paths,
            object_path=lambda path: path,
            operation=self._read_bytes,
        )

    def write_many(self, items: Iterable[tuple[str, bytes]], overwrite: bool = False) -> list[StorageBatchResult]:
        """兼容旧命名；新代码优先使用 batch_write_bytes。"""
        return self.batch_write_bytes(items, overwrite)

    def read_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """兼容旧命名；新代码优先使用 batch_read_bytes。"""
        return self.batch_read_bytes(object_paths)

    def exists_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """批量检查对象是否存在，单项异常不影响整批检查。"""
        return _collect_batch_results(
            object_paths,
            object_path=lambda path: path,
            operation=self.exists,
        )

    def delete_many(self, object_paths: Iterable[str]) -> list[StorageBatchResult]:
        """批量删除对象，逐项记录删除结果。"""
        return _collect_batch_results(
            object_paths,
            object_path=lambda path: path,
            operation=self.delete,
        )
