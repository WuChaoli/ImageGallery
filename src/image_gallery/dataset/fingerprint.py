import hashlib

import pandas as pd


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    """基于排序后的列和行内容生成稳定指纹。"""
    normalized = frame.reindex(sorted(frame.columns), axis=1)
    csv_bytes = normalized.sort_values(by=list(normalized.columns)).to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()
