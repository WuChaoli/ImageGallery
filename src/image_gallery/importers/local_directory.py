from pathlib import Path

from image_gallery.importers.config import SourceRecord


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


class LocalDirectoryReader:
    """递归扫描本地目录中的图片文件。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def read(self) -> list[SourceRecord]:
        """读取目录下支持的图片后缀，并按路径排序保证结果稳定。"""
        records: list[SourceRecord] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue
            records.append(
                SourceRecord(
                    source_uri=str(path),
                    source_type="local_directory",
                    source_file_name=path.name,
                    source_relative_path=path.relative_to(self.root).as_posix(),
                    local_path=path,
                )
            )
        return records
