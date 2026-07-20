"""Dataset 名称规范化规则。"""

from image_gallery.dataset_manager.errors import ValidationError


def normalize_dataset_name(name: str) -> str:
    """返回去除首尾空白的 Dataset 显示名称。"""
    normalized = name.strip()
    if not normalized:
        raise ValidationError("Dataset name cannot be empty")
    return normalized


def dataset_name_key(name: str) -> str:
    """返回 Dataset 在 Repo 内的大小写无关唯一键。"""
    return normalize_dataset_name(name).casefold()
