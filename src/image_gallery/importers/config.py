from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceRecord:
    """外部图片来源条目，导入前不承载清洗语义。"""

    source_uri: str
    source_type: str
    source_file_name: str
    source_relative_path: str
    local_path: Path | None = None
