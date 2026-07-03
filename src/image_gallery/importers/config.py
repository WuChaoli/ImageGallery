from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SourceRecord:
    """外部图片来源条目，导入前不承载清洗语义。"""

    source_uri: str
    source_type: str
    source_file_name: str
    source_relative_path: str
    local_path: Path | None = None


@runtime_checkable
class SourceParser(Protocol):
    """把外部输入解析为 SourceRecord 列表的统一协议。"""

    def parse(self) -> list[SourceRecord]:
        """解析外部图片来源。"""
        ...
