"""Cleaning namespace for ImageGallery."""

__all__ = [
    "BasicCleaner",
    "Cleaner",
    "PreviewResult",
]


def __getattr__(name: str) -> object:
    """按需导出清洗公开入口，避免 operators 初始化时出现循环导入。"""
    if name == "BasicCleaner":
        from image_gallery.cleaning.basic import BasicCleaner

        return BasicCleaner
    if name == "Cleaner":
        from image_gallery.cleaning.cleaner import Cleaner

        return Cleaner
    if name == "PreviewResult":
        from image_gallery.cleaning.preview import PreviewResult

        return PreviewResult
    raise AttributeError(name)
