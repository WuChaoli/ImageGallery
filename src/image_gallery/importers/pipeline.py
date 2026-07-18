from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from image_gallery.importers._pipeline_steps import (
    import_record as _import_record,
)
from image_gallery.importers._pipeline_steps import (
    write_import_artifacts as _write_import_artifacts,
)
from image_gallery.importers.config import SourceParser
from image_gallery.importers.local_path import LocalPathParser
from image_gallery.importers.report import ImportResult
from image_gallery.storage import Storage


class ImportPipeline:
    """把外部图片来源导入受管 storage 并生成 raw Dataset。"""

    def __init__(
        self,
        source: SourceParser | str | Path,
        storage: Storage,
        output_dir: str | Path,
        global_tags: Iterable[str] | None = None,
        max_shard_size: int = 10000,
        prefix: str = "images/raw",
    ) -> None:
        self.source_parser = _normalize_source_parser(source)
        self.storage = storage
        self.output_dir = Path(output_dir)
        self.global_tags = _unique_tags(global_tags or [])
        if max_shard_size <= 0:
            raise ValueError("max_shard_size must be greater than 0")
        self.max_shard_size = max_shard_size
        self.prefix = _normalize_prefix(prefix)

    def run(self) -> ImportResult:
        """执行 copy 模式导入，并写出 raw Dataset、报告和失败清单。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        records = self.source_parser.parse()
        import_date = datetime.now().date().isoformat()
        imported_rows: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        for record in records:
            imported_at = datetime.now(timezone.utc).isoformat()
            result = _import_record(
                record,
                storage=self.storage,
                global_tags=self.global_tags,
                prefix=self.prefix,
                import_date=import_date,
                shard_index=len(imported_rows) // self.max_shard_size + 1,
                imported_at=imported_at,
            )
            if result.row is not None:
                imported_rows.append(result.row)
            elif result.failure is not None:
                failures.append(result.failure)

        return _write_import_artifacts(
            self.output_dir,
            imported_rows=imported_rows,
            failures=failures,
        )


def _normalize_source_parser(source: SourceParser | str | Path) -> SourceParser:
    """把用户输入归一化为 SourceParser。"""
    if isinstance(source, (str, Path)):
        return LocalPathParser(source)
    if isinstance(source, SourceParser):
        return source
    raise TypeError("source must be a SourceParser or local path")


def _unique_tags(tags: Iterable[str]) -> list[str]:
    """按输入顺序去重 global_tags。"""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def _normalize_prefix(prefix: str) -> str:
    """规范化 raw 图片写入前缀。"""
    return prefix.strip("/")
