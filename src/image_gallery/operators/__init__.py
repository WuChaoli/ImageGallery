"""Operator namespace for ImageGallery."""

from image_gallery.operators.builtin import create_default_metric_specs, create_default_registry
from image_gallery.operators.metric_spec import MetricSpec, relative_to_absolute
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec

__all__ = [
    "MetricSpec",
    "OperatorRegistry",
    "OperatorSpec",
    "create_default_metric_specs",
    "create_default_registry",
    "relative_to_absolute",
]
