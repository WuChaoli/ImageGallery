from pathlib import Path

from image_gallery.importers.config import SourceRecord

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


class LocalPathParser:
    """解析本地文件或目录图片来源。"""

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source).expanduser().resolve()

    def parse(self) -> list[SourceRecord]:
        """解析本地目录或单个图片文件。"""
        if not self.source.exists():
            raise FileNotFoundError(self.source)
        if self.source.is_file():
            return [self._record_for_file(self.source, self.source.parent)]

        records: list[SourceRecord] = []
        for path in sorted(self.source.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue
            records.append(self._record_for_file(path, self.source))
        return records

    def _record_for_file(self, path: Path, root: Path) -> SourceRecord:
        """把单个本地图片文件转换为 SourceRecord。"""
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError(f"unsupported image extension: {path.name}")
        return SourceRecord(
            source_uri=str(path),
            source_type="local_path",
            source_file_name=path.name,
            source_relative_path=path.relative_to(root).as_posix(),
            local_path=path,
        )
