"""Cleaning namespace for ImageGallery."""

__all__ = [
    "ActionRange",
    "BasicCleaner",
    "Cleaner",
    "CleanerExecution",
    "CleanerRecipe",
    "CleanerResult",
    "DiskRunStore",
    "DryRunResult",
    "MemoryRunStore",
    "PreviewResult",
    "RunStore",
    "TemporaryRunStore",
    "evaluate_with_rules",
]


def __getattr__(name: str) -> object:
    """按需导出清洗公开入口，避免 operators 初始化时出现循环导入。"""
    if name == "ActionRange":
        from image_gallery.cleaning.action_range import ActionRange

        return ActionRange
    if name == "BasicCleaner":
        from image_gallery.cleaning.basic import BasicCleaner

        return BasicCleaner
    if name == "Cleaner":
        from image_gallery.cleaning.cleaner import Cleaner

        return Cleaner
    if name == "CleanerExecution":
        from image_gallery.cleaning.execution import CleanerExecution

        return CleanerExecution
    if name == "CleanerRecipe":
        from image_gallery.cleaning.recipe import CleanerRecipe

        return CleanerRecipe
    if name == "CleanerResult":
        from image_gallery.cleaning.result import CleanerResult

        return CleanerResult
    if name == "DiskRunStore":
        from image_gallery.cleaning.run_store import DiskRunStore

        return DiskRunStore
    if name == "DryRunResult":
        from image_gallery.cleaning.execution import DryRunResult

        return DryRunResult
    if name == "MemoryRunStore":
        from image_gallery.cleaning.run_store import MemoryRunStore

        return MemoryRunStore
    if name == "PreviewResult":
        from image_gallery.cleaning.preview import PreviewResult

        return PreviewResult
    if name == "RunStore":
        from image_gallery.cleaning.run_store import RunStore

        return RunStore
    if name == "TemporaryRunStore":
        from image_gallery.cleaning.run_store import TemporaryRunStore

        return TemporaryRunStore
    if name == "evaluate_with_rules":
        from image_gallery.cleaning.rule_evaluator import evaluate_with_rules

        return evaluate_with_rules
    raise AttributeError(name)
