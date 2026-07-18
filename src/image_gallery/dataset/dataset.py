from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

import pandas as pd
from PIL import Image

from image_gallery.dataset._tabular_io import (
    format_from_path as _format_from_path,
)
from image_gallery.dataset._tabular_io import (
    read_frame as _read_frame,
)
from image_gallery.dataset._tabular_io import (
    write_frame as _write_frame,
)
from image_gallery.dataset.fingerprint import dataframe_fingerprint
from image_gallery.dataset.io import DatasetExporter, DatasetExportResult, DatasetLoader
from image_gallery.storage.base import Storage
from image_gallery.storage.uri import file_image_uri_to_path


@dataclass(frozen=True)
class DatasetImageBytesReadResult:
    """图片 bytes 批量读取结果，单张失败不影响整批。"""

    image_uri: str
    ok: bool
    data: bytes | None = None
    error: str | None = None


@dataclass(frozen=True)
class DatasetImageReadResult:
    """图片对象批量读取结果，单张失败不影响整批。"""

    image_uri: str
    ok: bool
    image: Image.Image | None = None
    error: str | None = None


@dataclass(frozen=True)
class ParsedImageUri:
    """Dataset 内部使用的图片地址解析结果。"""

    kind: str
    image_uri: str
    local_path: Path | None = None
    bucket: str | None = None
    object_path: str | None = None


@dataclass(frozen=True)
class DatasetImage:
    """Dataset 中按行枚举出的图片对象。"""

    image_id: str
    image_uri: str
    row: dict[str, object]
    dataset: "Dataset"

    def read_bytes(self) -> bytes:
        """读取当前图片 bytes。"""
        return self.dataset.read_image_bytes(self.image_uri)

    def read_image(self) -> Image.Image:
        """读取当前图片为 Pillow Image。"""
        return self.dataset.read_image(self.image_uri)


@dataclass(frozen=True)
class Dataset:
    """数据集文件的轻量封装，不表达 raw、clean、dropped、full 阶段语义。"""

    # dataset_path 是数据集文件路径，当前阶段主要支持本地 Parquet/CSV/JSONL。
    dataset_path: str
    # format 是由文件扩展名推导出的数据集格式，用于选择 Pandas 读写方法。
    format: str = "parquet"
    # storage 是可选图片对象读取依赖；本地路径不需要 storage。
    storage: Storage | None = field(default=None, compare=False, repr=False)

    @classmethod
    def load(cls, source: str | Path | DatasetLoader, storage: Storage | None = None) -> "Dataset":
        """从表格文件或 DatasetLoader 加载 Dataset。"""
        if isinstance(source, DatasetLoader):
            return source.load()
        dataset_path = str(source)
        return cls(dataset_path=dataset_path, format=_format_from_path(dataset_path), storage=storage)

    @classmethod
    def write(cls, data: pd.DataFrame, output_path: str, storage: Storage | None = None) -> "Dataset":
        """把 DataFrame 写出为数据集文件，并返回对应 Dataset 对象。"""
        # resolved_output_path 是实际写入位置；父目录不存在时自动创建。
        resolved_output_path = Path(output_path)
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        # file_format 决定本次写出使用 Parquet、CSV 还是 JSONL。
        file_format = _format_from_path(output_path)
        _write_frame(data, resolved_output_path, file_format)
        return cls(dataset_path=output_path, format=file_format, storage=storage)

    def to_frame(self, columns: list[str] | None = None) -> pd.DataFrame:
        """读取完整数据集；传入 columns 时只返回指定列。"""
        # frame 是从磁盘读取出来的内存 DataFrame，后续筛选都基于它完成。
        frame = _read_frame(self.dataset_path, self.format)
        if columns is not None:
            return cast(pd.DataFrame, frame[columns])
        return frame

    def read_image_bytes(self, image_uri: str) -> bytes:
        """根据 image_uri 读取图片 bytes。"""
        parsed = _parse_image_uri(image_uri)
        if parsed.kind == "local":
            if parsed.local_path is None:
                raise ValueError(f"local image_uri parsed without path: {image_uri}")
            return parsed.local_path.read_bytes()
        if parsed.kind == "s3":
            if self.storage is None:
                raise ValueError(f"storage is required for s3 image_uri: {image_uri}")
            if parsed.object_path is None:
                raise ValueError(f"s3 image_uri parsed without object_path: {image_uri}")
            return self.storage.read_bytes(parsed.object_path)
        raise ValueError(f"unsupported image_uri kind: {parsed.kind}")

    def read_image(self, image_uri: str) -> Image.Image:
        """根据 image_uri 读取图片并解码为 Pillow Image。"""
        data = self.read_image_bytes(image_uri)
        with Image.open(BytesIO(data)) as image:
            image.load()
            loaded = image.copy()
            loaded.format = image.format
            return loaded

    def read_image_bytes_batch(self, image_uris: Iterable[str]) -> list[DatasetImageBytesReadResult]:
        """批量读取图片 bytes，逐项返回成功值或错误信息。"""
        results: list[DatasetImageBytesReadResult] = []
        for image_uri in image_uris:
            try:
                data = self.read_image_bytes(image_uri)
                results.append(DatasetImageBytesReadResult(image_uri=image_uri, ok=True, data=data))
            # 批量读取必须隔离单张图片的 Storage 或解码失败。
            except Exception as exc:  # noqa: BLE001
                results.append(DatasetImageBytesReadResult(image_uri=image_uri, ok=False, error=str(exc)))
        return results

    def read_image_batch(self, image_uris: Iterable[str]) -> list[DatasetImageReadResult]:
        """批量读取图片对象，逐项返回成功值或错误信息。"""
        results: list[DatasetImageReadResult] = []
        for image_uri in image_uris:
            try:
                image = self.read_image(image_uri)
                results.append(DatasetImageReadResult(image_uri=image_uri, ok=True, image=image))
            # 批量读取必须隔离单张图片的 Storage 或解码失败。
            except Exception as exc:  # noqa: BLE001
                results.append(DatasetImageReadResult(image_uri=image_uri, ok=False, error=str(exc)))
        return results

    def iter_images(self, columns: list[str] | None = None) -> Iterator[DatasetImage]:
        """按 Dataset 当前行顺序枚举图片对象。"""
        required_columns = ["image_id", "image_uri"]
        selected_columns = required_columns if columns is None else [*required_columns, *columns]
        frame = self.to_frame(columns=_dedupe_columns(selected_columns))
        for row in cast(list[dict[str, object]], frame.to_dict(orient="records")):
            yield DatasetImage(
                image_id=str(row["image_id"]),
                image_uri=str(row["image_uri"]),
                row=row,
                dataset=self,
            )

    def scan(self, columns: list[str] | None = None, filters: dict[str, object] | None = None) -> pd.DataFrame:
        """读取数据集并按等值条件过滤，供后续模块做轻量扫描。"""
        # filters 采用最小等值过滤语义，例如 {"import_status": "imported"}。
        frame = self.to_frame()
        if filters:
            for column, value in filters.items():
                # column 是待过滤字段，value 是该字段必须匹配的目标值。
                frame = cast(pd.DataFrame, frame[frame[column] == value])
        if columns is not None:
            return cast(pd.DataFrame, frame[columns])
        return frame

    def preview(self, limit: int = 100) -> pd.DataFrame:
        """返回前 limit 行，用于 Notebook 或调试场景快速查看数据。"""
        return self.to_frame().head(limit)

    def count(self) -> int:
        """返回数据集行数。"""
        return len(self.to_frame())

    def validate_readable(self) -> None:
        """确认数据集文件存在且能被当前格式读取。"""
        # 先做路径存在性检查，避免 Pandas 抛出的底层错误缺少业务上下文。
        if not Path(self.dataset_path).exists():
            raise FileNotFoundError(self.dataset_path)
        # 读取一行即可验证格式和读权限，不需要把大文件全部载入内存。
        self.preview(limit=1)

    def fingerprint(self) -> str:
        """基于数据集内容生成稳定指纹，用于后续产物复用和变更判断。"""
        return dataframe_fingerprint(self.to_frame())

    def draw(
        self,
        filter: dict[str, object] | None = None,
        sort: dict[str, str] | None = None,
        size: tuple[int, int] | None = None,
        max_num: int = 24,
        image_column: str = "image_uri",
        caption_columns: list[str] | None = None,
        thumbnail_width: int = 160,
    ) -> object:
        """在 Notebook 中绘制指定数量的图片网格。"""
        # frame 按固定顺序处理：过滤 -> 排序 -> 截断 -> 渲染。
        frame = self.scan(filters=filter)
        frame = _sort_frame(frame, sort)
        row_limit, columns = _draw_limits(size=size, max_num=max_num)
        frame = frame.head(row_limit)

        from image_gallery.visualization import show_image_grid

        return show_image_grid(
            frame,
            limit=row_limit,
            image_column=image_column,
            caption_columns=caption_columns,
            thumbnail_width=thumbnail_width,
            columns=columns,
        )

    def export(self, exporter: DatasetExporter) -> DatasetExportResult:
        """使用指定 exporter 导出 Dataset。"""
        if not isinstance(exporter, DatasetExporter):
            raise TypeError("exporter must implement DatasetExporter")
        return exporter.export(self)


def _parse_image_uri(image_uri: str) -> ParsedImageUri:
    """解析 Dataset 支持的图片地址类型。"""
    parsed = urlparse(image_uri)
    if parsed.scheme == "s3":
        object_path = parsed.path.lstrip("/")
        if not parsed.netloc or not object_path:
            raise ValueError(f"invalid s3 image_uri: {image_uri}")
        return ParsedImageUri(
            kind="s3",
            image_uri=image_uri,
            bucket=parsed.netloc,
            object_path=unquote(object_path),
        )
    if parsed.scheme in {"", "file"} or (len(parsed.scheme) == 1 and parsed.scheme.isalpha()):
        return ParsedImageUri(kind="local", image_uri=image_uri, local_path=file_image_uri_to_path(image_uri))
    raise ValueError(f"unsupported image_uri scheme: {parsed.scheme}")


def _dedupe_columns(columns: list[str]) -> list[str]:
    """保持顺序去重，避免用户 columns 重复包含 image_id 或 image_uri。"""
    deduped: list[str] = []
    for column in columns:
        if column not in deduped:
            deduped.append(column)
    return deduped


def _sort_frame(frame: pd.DataFrame, sort: dict[str, str] | None) -> pd.DataFrame:
    """按单字段排序 DataFrame。"""
    if not sort:
        return frame
    if len(sort) != 1:
        raise ValueError("sort supports exactly one column in the first version")

    column, direction = next(iter(sort.items()))
    normalized_direction = direction.lower()
    if normalized_direction not in {"asc", "desc"}:
        raise ValueError(f"unsupported sort direction: {direction}")
    return frame.sort_values(by=column, ascending=normalized_direction == "asc")


def _draw_limits(*, size: tuple[int, int] | None, max_num: int) -> tuple[int, int | None]:
    """根据行列 size 和 max_num 计算渲染数量与列数。"""
    if max_num < 0:
        raise ValueError("max_num must not be negative")
    if size is None:
        return max_num, None

    rows, columns = size
    if rows <= 0 or columns <= 0:
        raise ValueError("size rows and columns must be greater than 0")
    return min(rows * columns, max_num), columns
