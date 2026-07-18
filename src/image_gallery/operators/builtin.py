from __future__ import annotations

from image_gallery.operators._builtin_evaluators import (
    evaluate_animated_image_check as evaluate_animated_image_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_aspect_ratio_check as evaluate_aspect_ratio_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_blank_image_check as evaluate_blank_image_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_blur_check as evaluate_blur_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_border_padding_check as evaluate_border_padding_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_brightness_check as evaluate_brightness_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_contrast_check as evaluate_contrast_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_decode_check as evaluate_decode_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_dimension_check as evaluate_dimension_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_exact_duplicate_check as evaluate_exact_duplicate_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_exposure_check as evaluate_exposure_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_megapixel_check as evaluate_megapixel_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_mono_color_check as evaluate_mono_color_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_noise_check as evaluate_noise_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_orientation_check as evaluate_orientation_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_perceptual_duplicate_check as evaluate_perceptual_duplicate_check,
)
from image_gallery.operators._builtin_evaluators import (
    evaluate_semantic_duplicate_check as evaluate_semantic_duplicate_check,
)
from image_gallery.operators._builtin_metrics import create_builtin_metric_specs
from image_gallery.operators._builtin_specs import create_builtin_operator_specs
from image_gallery.operators.computers.border import ImageBorderComputer
from image_gallery.operators.computers.derived import TableDerivedComputer
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer, PerceptualDuplicateGroupComputer
from image_gallery.operators.computers.hash import ImageHashComputer, ImagePerceptualHashComputer
from image_gallery.operators.computers.metadata import ImageFormatDetailComputer, ImageMetadataComputer
from image_gallery.operators.computers.quality import ImageQualityComputer, ImageQualityDetailComputer
from image_gallery.operators.computers.semantic import SemanticDuplicateGroupComputer, SemanticEmbeddingComputer
from image_gallery.operators.metric_spec import MetricSpec
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider


def create_default_registry(
    semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
) -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
    registry = OperatorRegistry()
    registry.register_parameter_computer(ImageMetadataComputer())
    registry.register_parameter_computer(TableDerivedComputer())
    registry.register_parameter_computer(ImageQualityComputer())
    registry.register_parameter_computer(ImageQualityDetailComputer())
    registry.register_parameter_computer(ImageBorderComputer())
    registry.register_parameter_computer(ImageFormatDetailComputer())
    registry.register_parameter_computer(ImageHashComputer())
    registry.register_parameter_computer(ImagePerceptualHashComputer())
    registry.register_parameter_computer(DuplicateGroupComputer())
    registry.register_parameter_computer(PerceptualDuplicateGroupComputer())
    registry.register_parameter_computer(SemanticEmbeddingComputer(semantic_providers))
    registry.register_parameter_computer(SemanticDuplicateGroupComputer())
    for spec in create_builtin_operator_specs():
        registry.register_operator(spec)
    return registry


def create_default_metric_specs() -> dict[str, MetricSpec]:
    """返回 17 个内置算子的 MetricSpec 注册表。

    键为算子名，值为该算子的主指标 MetricSpec。
    """
    return create_builtin_metric_specs()
