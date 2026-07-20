from image_gallery.operators.metric_spec import MetricSpec


def create_builtin_metric_specs() -> dict[str, MetricSpec]:
    """返回 17 个内置算子的 MetricSpec 注册表。

    键为算子名，值为该算子的主指标 MetricSpec。
    """
    return {
        # 格式类
        "decode": MetricSpec(
            name="decode_ok",
            value_type="categorical",
            direction="categorical",
        ),
        "animated": MetricSpec(
            name="animated",
            value_type="categorical",
            direction="categorical",
        ),
        # 尺寸类
        "dimension": MetricSpec(
            name="min_width",
            value_type="absolute",
            direction="higher_better",
        ),
        "aspect_ratio": MetricSpec(
            name="aspect_ratio",
            value_type="absolute",
            direction="higher_better",
        ),
        "megapixel": MetricSpec(
            name="megapixels",
            value_type="absolute",
            direction="higher_better",
        ),
        # 质量类
        "blur": MetricSpec(
            name="blur_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=300.0,
        ),
        "brightness": MetricSpec(
            name="brightness_score",
            value_type="absolute",
            direction="higher_better",
        ),
        "contrast": MetricSpec(
            name="contrast_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=100.0,
        ),
        "exposure": MetricSpec(
            name="dark_pixel_ratio",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
        "noise": MetricSpec(
            name="noise_score",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
        # 内容类
        "blank": MetricSpec(
            name="blank_score",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
        "mono_color": MetricSpec(
            name="mono_color_score",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
        "border_padding": MetricSpec(
            name="border_padding_ratio",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
        # 元数据类
        "orientation": MetricSpec(
            name="orientation_risk",
            value_type="categorical",
            direction="categorical",
        ),
        # 去重类
        "exact_duplicate": MetricSpec(
            name="exact_duplicate_count",
            value_type="categorical",
            direction="categorical",
        ),
        "perceptual_duplicate": MetricSpec(
            name="perceptual_duplicate_distance",
            value_type="relative",
            direction="lower_better",
            absolute_min=0.0,
            absolute_max=100.0,
        ),
        "semantic_duplicate": MetricSpec(
            name="semantic_duplicate_score",
            value_type="relative",
            direction="higher_better",
            absolute_min=0.0,
            absolute_max=1.0,
        ),
    }
