"""Cleaning namespace for ImageGallery."""

__all__ = [
    "BasicCleaner",
    "Cleaner",
    "CleanerExecution",
    "CleanerResult",
    "DryRunResult",
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
    if name == "CleanerExecution":
        from image_gallery.cleaning.execution import CleanerExecution

        return CleanerExecution
    if name == "CleanerResult":
        from image_gallery.cleaning.result import CleanerResult

        return CleanerResult
    if name == "DryRunResult":
        from image_gallery.cleaning.execution import DryRunResult

        return DryRunResult
    if name == "PreviewResult":
        from image_gallery.cleaning.preview import PreviewResult

        return PreviewResult
    raise AttributeError(name)
