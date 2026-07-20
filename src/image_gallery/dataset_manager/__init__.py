"""不受旧 Dataset API 限制的新数据集管理平台。

MVP 不提供 merge、跨 Repo clone、完整历史继承、diff、rebase、cherry-pick、stash、
删除、archive、retention、引用计数、GC、历史向量、ANN
或语义搜索；这些能力需要独立 OpenSpec change。
"""

from image_gallery.dataset_manager._physical_schema import (
    ColumnSpec,
    ListFieldType,
    PrimitiveFieldType,
    StructField,
    StructFieldType,
)
from image_gallery.dataset_manager.errors import (
    ConflictError,
    DatasetManagerError,
    NameConflictError,
    ObjectNotFoundError,
    StorageAuthorizationError,
    ValidationError,
)
from image_gallery.dataset_manager.manager import DatasetManager
from image_gallery.dataset_manager.models import (
    CommitMode,
    CommitResult,
    Dataset,
    DatasetRepo,
    DatasetSchema,
    DatasetView,
    EmbedResult,
    RepoSchema,
    TagDefinition,
    VectorField,
)

__all__ = [
    "ColumnSpec",
    "CommitResult",
    "CommitMode",
    "ConflictError",
    "Dataset",
    "DatasetManager",
    "DatasetManagerError",
    "DatasetRepo",
    "DatasetSchema",
    "DatasetView",
    "EmbedResult",
    "ListFieldType",
    "NameConflictError",
    "ObjectNotFoundError",
    "PrimitiveFieldType",
    "RepoSchema",
    "StorageAuthorizationError",
    "StructField",
    "StructFieldType",
    "TagDefinition",
    "ValidationError",
    "VectorField",
]
