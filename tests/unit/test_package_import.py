import importlib

import image_gallery


def test_package_exposes_version() -> None:
    assert image_gallery.__version__ == "0.1.0"


def test_stage0_module_names_are_importable() -> None:
    module_names = [
        "image_gallery.config",
        "image_gallery.storage",
        "image_gallery.dataset",
        "image_gallery.schemas",
        "image_gallery.state",
        "image_gallery.importers",
        "image_gallery.cleaning",
        "image_gallery.operators",
        "image_gallery.visualization",
        "image_gallery.reports",
        "image_gallery.utils",
    ]

    for module_name in module_names:
        assert importlib.import_module(module_name).__name__ == module_name


def test_notebook_helper_modules_are_importable() -> None:
    module_names = [
        "notebooks",
        "notebooks._helpers",
        "notebooks._helpers.paths",
        "notebooks._helpers.storage",
        "notebooks._helpers.datasets",
        "notebooks._helpers.cleaning_configs",
    ]

    for module_name in module_names:
        assert importlib.import_module(module_name).__name__ == module_name
