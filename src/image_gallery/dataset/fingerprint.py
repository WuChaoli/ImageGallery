import hashlib
import json
from typing import Any

import pandas as pd


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    """基于排序后的列和行内容生成稳定指纹。"""
    normalized = frame.reindex(sorted(frame.columns), axis=1)
    normalized = normalized.map(_normalize_cell)
    csv_bytes = normalized.sort_values(by=list(normalized.columns)).to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _normalize_cell(value: Any) -> Any:
    """把嵌套值转成可排序、可序列化的稳定表示。"""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
