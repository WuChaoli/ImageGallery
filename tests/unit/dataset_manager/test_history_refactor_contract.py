import importlib
import importlib.util
from pathlib import Path

from image_gallery.dataset_manager import DatasetManager
from image_gallery.storage_manager import StorageManager


def test_manager_composes_private_dataset_history(tmp_path: Path) -> None:
    spec = importlib.util.find_spec("image_gallery.dataset_manager._dataset_history")
    assert spec is not None
    history_module = importlib.import_module("image_gallery.dataset_manager._dataset_history")
    history_type = history_module.DatasetHistory
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=StorageManager())

    assert isinstance(manager._history, history_type)
    assert manager._history.catalog is manager.catalog
    forbidden = {
        "add_column",
        "archive_tag",
        "create_tag",
        "create_vector_field",
        "generate_embed",
        "read_image",
        "rename_tag",
        "scan",
    }

    assert forbidden.isdisjoint(vars(history_type))
