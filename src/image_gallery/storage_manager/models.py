"""StorageManager 公共值对象。"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class StoragePrefix:
    """描述稳定的存储根，不包含明文凭证。"""

    prefix_id: str
    name: str
    backend: Literal["file", "s3", "sftp"]
    root: str
    credential_ref: str | None = None
    endpoint_url: str | None = None


@dataclass(frozen=True, slots=True)
class StoredObject:
    """描述已经过内容身份验证的图片对象。"""

    asset_id: str
    storage_prefix_id: str
    relative_path: str
