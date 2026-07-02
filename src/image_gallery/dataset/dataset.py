from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from image_gallery.dataset.fingerprint import dataframe_fingerprint


@dataclass(frozen=True)
class Dataset:
    """数据集文件的轻量封装，不表达 raw、clean、dropped、full 阶段语义。"""

    # dataset_path 是数据集文件路径，当前阶段主要支持本地 Parquet/CSV/JSONL。
    dataset_path: str
    # format 是由文件扩展名推导出的数据集格式，用于选择 Pandas 读写方法。
    format: str = "parquet"

    @classmethod
    def from_path(cls, dataset_path: str) -> "Dataset":
        """从已有数据集路径创建 Dataset 对象，不立即读取文件内容。"""
        return cls(dataset_path=dataset_path, format=_format_from_path(dataset_path))

    @classmethod
    def write(cls, data: pd.DataFrame, output_path: str) -> "Dataset":
        """把 DataFrame 写出为数据集文件，并返回对应 Dataset 对象。"""
        # resolved_output_path 是实际写入位置；父目录不存在时自动创建。
        resolved_output_path = Path(output_path)
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        # file_format 决定本次写出使用 Parquet、CSV 还是 JSONL。
        file_format = _format_from_path(output_path)
        if file_format == "parquet":
            data.to_parquet(resolved_output_path, index=False)
        elif file_format == "csv":
            data.to_csv(resolved_output_path, index=False)
        elif file_format == "jsonl":
            data.to_json(resolved_output_path, orient="records", lines=True, force_ascii=False)
        else:
            raise ValueError(f"unsupported dataset format: {file_format}")
        return cls(dataset_path=output_path, format=file_format)

    def to_frame(self, columns: list[str] | None = None) -> pd.DataFrame:
        """读取完整数据集；传入 columns 时只返回指定列。"""
        # frame 是从磁盘读取出来的内存 DataFrame，后续筛选都基于它完成。
        frame = _read_frame(self.dataset_path, self.format)
        if columns is not None:
            return frame[columns]
        return frame

    def scan(self, columns: list[str] | None = None, filters: dict[str, object] | None = None) -> pd.DataFrame:
        """读取数据集并按等值条件过滤，供后续模块做轻量扫描。"""
        # filters 采用最小等值过滤语义，例如 {"import_status": "imported"}。
        frame = self.to_frame()
        if filters:
            for column, value in filters.items():
                # column 是待过滤字段，value 是该字段必须匹配的目标值。
                frame = frame[frame[column] == value]
        if columns is not None:
            return frame[columns]
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

    def export(self, output_dataset_path: str, address_policy: str = "keep") -> "Dataset":
        """导出数据集；默认保留 image_uri 并移除 source_uri。"""
        # address_policy 当前只支持 keep：保留 image_uri，不复制或改写图片地址。
        if address_policy != "keep":
            raise ValueError(f"unsupported address_policy: {address_policy}")
        # frame 是待导出的数据；source_uri 默认属于追溯字段，对外导出时移除。
        frame = self.to_frame()
        if "source_uri" in frame.columns:
            frame = frame.drop(columns=["source_uri"])
        return Dataset.write(frame, output_dataset_path)


def _format_from_path(dataset_path: str) -> str:
    """根据数据集路径后缀推导文件格式。"""
    # suffix 统一转小写，避免 .CSV、.Parquet 这类大小写差异影响判断。
    suffix = Path(dataset_path).suffix.lower()
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".csv":
        return "csv"
    if suffix in {".jsonl", ".json"}:
        return "jsonl"
    raise ValueError(f"unsupported dataset extension: {suffix}")


def _read_frame(dataset_path: str, file_format: str) -> pd.DataFrame:
    """按指定格式读取数据集文件为 DataFrame。"""
    if file_format == "parquet":
        return pd.read_parquet(dataset_path)
    if file_format == "csv":
        return pd.read_csv(dataset_path)
    if file_format == "jsonl":
        return pd.read_json(dataset_path, lines=True)
    raise ValueError(f"unsupported dataset format: {file_format}")


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
