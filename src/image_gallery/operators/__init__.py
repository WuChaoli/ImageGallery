"""Operator namespace for ImageGallery."""

from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec

__all__ = [
    "OperatorRegistry",
    "OperatorSpec",
    "create_default_registry",
]
