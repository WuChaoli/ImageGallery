from __future__ import annotations

from typing import Any, cast

import pandas as pd


def evaluate_decode_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 decode_ok 生成解码检查结果。"""
    action = str(config.get("action", "drop"))
    failed = ~parameter_table["decode_ok"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "decode_action": failed.map(lambda value: action if value else "keep"),
            "decode_reason": parameter_table["decode_error"].where(failed, ""),
        }
    )


def evaluate_dimension_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 width、height 和阈值生成尺寸检查结果。"""
    min_width = _as_int(config.get("min_width", 1))
    min_height = _as_int(config.get("min_height", 1))
    action = str(config.get("action", "drop"))
    widths = cast(pd.Series, pd.to_numeric(parameter_table["width"], errors="coerce")).fillna(0)
    heights = cast(pd.Series, pd.to_numeric(parameter_table["height"], errors="coerce")).fillna(0)
    failed = cast(pd.Series, (widths < min_width) | (heights < min_height))
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "dimension_action": failed.map(lambda value: action if value else "keep"),
            "dimension_reason": failed.map(lambda value: f"smaller than {min_width}x{min_height}" if value else ""),
        }
    )


def evaluate_aspect_ratio_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 aspect_ratio 生成宽高比检查结果。"""
    min_ratio = _as_float(config.get("min_ratio", 0.2))
    max_ratio = _as_float(config.get("max_ratio", 5.0))
    action = str(config.get("action", "review"))
    ratios = cast(pd.Series, pd.to_numeric(parameter_table["aspect_ratio"], errors="coerce"))
    failed = cast(pd.Series, ratios.notna() & ((ratios < min_ratio) | (ratios > max_ratio)))
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "aspect_ratio": ratios,
            "aspect_ratio_action": failed.map(lambda value: action if value else "keep"),
            "aspect_ratio_reason": failed.map(
                lambda value: f"aspect ratio outside {min_ratio}..{max_ratio}" if value else ""
            ),
        }
    )


def evaluate_megapixel_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 megapixels 生成像素量检查结果。"""
    min_megapixels = _as_float(config.get("min_megapixels", 0.01))
    max_value = config.get("max_megapixels")
    max_megapixels = None if max_value is None else _as_float(max_value)
    action = str(config.get("action", "review"))
    megapixels = cast(pd.Series, pd.to_numeric(parameter_table["megapixels"], errors="coerce"))
    failed = cast(pd.Series, megapixels.notna() & (megapixels < min_megapixels))
    if max_megapixels is not None:
        failed = cast(pd.Series, failed | (megapixels.notna() & (megapixels > max_megapixels)))
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "megapixels": megapixels,
            "megapixel_action": failed.map(lambda value: action if value else "keep"),
            "megapixel_reason": failed.map(lambda value: "megapixels outside configured range" if value else ""),
        }
    )


def evaluate_blur_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 blur_score 生成模糊检查结果。"""
    min_score = _as_float(config.get("min_score", 100.0))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["blur_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores < min_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "blur", action, f"blur score below {min_score}"
    )


def evaluate_brightness_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 brightness_score 生成亮度检查结果。"""
    min_score = _as_float(config.get("min_score", 30.0))
    max_score = _as_float(config.get("max_score", 225.0))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["brightness_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & ((scores < min_score) | (scores > max_score)))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
        scores,
        failed,
        "brightness",
        action,
        f"brightness outside {min_score}..{max_score}",
    )


def evaluate_contrast_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 contrast_score 生成对比度检查结果。"""
    min_score = _as_float(config.get("min_score", 10.0))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["contrast_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores < min_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
        scores,
        failed,
        "contrast",
        action,
        f"contrast score below {min_score}",
    )


def evaluate_blank_image_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 blank_score 生成空白图检查结果。"""
    threshold = _as_float(config.get("threshold", 0.98))
    action = str(config.get("action", "drop"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["blank_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores >= threshold))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
        scores,
        failed,
        "blank",
        action,
        f"blank score at least {threshold}",
    )


def evaluate_exposure_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据暗部、亮部和截断像素比例生成曝光检查结果。"""
    max_dark = _as_float(config.get("max_dark_pixel_ratio", 0.95))
    max_bright = _as_float(config.get("max_bright_pixel_ratio", 0.95))
    max_clipped = _as_float(config.get("max_clipped_pixel_ratio", 0.98))
    action = str(config.get("action", "review"))
    dark = cast(pd.Series, pd.to_numeric(parameter_table["dark_pixel_ratio"], errors="coerce"))
    bright = cast(pd.Series, pd.to_numeric(parameter_table["bright_pixel_ratio"], errors="coerce"))
    clipped = cast(pd.Series, pd.to_numeric(parameter_table["clipped_pixel_ratio"], errors="coerce"))
    failed = cast(pd.Series, (dark > max_dark) | (bright > max_bright) | (clipped > max_clipped))
    reasons = [
        _exposure_reason(dark_value, bright_value, clipped_value, max_dark, max_bright, max_clipped)
        if failed_value
        else ""
        for dark_value, bright_value, clipped_value, failed_value in zip(
            dark.tolist(), bright.tolist(), clipped.tolist(), failed.tolist(), strict=True
        )
    ]
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "dark_pixel_ratio": dark,
            "bright_pixel_ratio": bright,
            "clipped_pixel_ratio": clipped,
            "exposure_action": failed.map(lambda value: action if value else "keep"),
            "exposure_reason": reasons,
        }
    )


def evaluate_noise_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 noise_score 生成噪声检查结果。"""
    max_score = _as_float(config.get("max_score", 0.75))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["noise_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores > max_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "noise", action, f"noise score above {max_score}"
    )


def evaluate_mono_color_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 mono_color_score 生成近单色检查结果。"""
    threshold = _as_float(config.get("threshold", 0.98))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["mono_color_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores >= threshold))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
        scores,
        failed,
        "mono_color",
        action,
        f"mono color score at least {threshold}",
    )


def evaluate_border_padding_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据边框留白比例生成边框检查结果。"""
    max_ratio = _as_float(config.get("max_ratio", 0.25))
    raw_colors = config.get("colors", ["white", "black", "solid"])
    colors = {str(color) for color in raw_colors} if isinstance(raw_colors, (list, tuple, set)) else {str(raw_colors)}
    action = str(config.get("action", "review"))
    ratios = cast(pd.Series, pd.to_numeric(parameter_table["border_padding_ratio"], errors="coerce"))
    sides = parameter_table["border_padding_sides"].fillna("").astype(str)
    border_colors = parameter_table["border_padding_color"].fillna("unknown").astype(str)
    side_counts = sides.map(lambda value: 0 if not value else len(value.split(",")))
    failed = cast(
        pd.Series, ratios.notna() & (ratios > max_ratio) & (side_counts > 0) & border_colors.isin(list(colors))
    )
    reasons = [
        f"border padding ratio above {max_ratio} sides={side_value} color={color_value}" if failed_value else ""
        for side_value, color_value, failed_value in zip(
            sides.tolist(), border_colors.tolist(), failed.tolist(), strict=True
        )
    ]
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "border_padding_ratio": ratios,
            "border_padding_sides": sides,
            "border_padding_color": border_colors,
            "border_padding_action": failed.map(lambda value: action if value else "keep"),
            "border_padding_reason": reasons,
        }
    )


def evaluate_animated_image_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 animated 标记生成多帧图片检查结果。"""
    action = str(config.get("action", "review"))
    frame_count = cast(pd.Series, pd.to_numeric(parameter_table["frame_count"], errors="coerce"))
    animated = parameter_table["animated"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "frame_count": frame_count,
            "animated": animated,
            "animated_action": animated.map(lambda value: action if value else "keep"),
            "animated_reason": animated.map(lambda value: "animated image" if value else ""),
        }
    )


def evaluate_orientation_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 EXIF orientation 风险生成方向检查结果。"""
    action = str(config.get("action", "review"))
    orientations = cast(pd.Series, pd.to_numeric(parameter_table["exif_orientation"], errors="coerce"))
    risk = parameter_table["orientation_risk"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "exif_orientation": orientations,
            "orientation_risk": risk,
            "orientation_action": risk.map(lambda value: action if value else "keep"),
            "orientation_reason": [
                f"exif orientation {int(orientation)}" if risk_value and pd.notna(orientation) else ""
                for orientation, risk_value in zip(orientations.tolist(), risk.tolist(), strict=True)
            ],
        }
    )


def evaluate_exact_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据完全重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("exact_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    groups = parameter_table["exact_duplicate_group_id"].fillna("").astype(str)
    counts = (
        cast(pd.Series, pd.to_numeric(parameter_table["exact_duplicate_count"], errors="coerce")).fillna(1).astype(int)
    )

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count in zip(groups.tolist(), counts.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"duplicate in group {group_id}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "exact_duplicate_group_id": groups,
            "exact_duplicate_count": counts,
            "exact_duplicate_action": actions,
            "exact_duplicate_reason": reasons,
        }
    )


def evaluate_perceptual_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据视觉近重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("perceptual_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action != "drop":
        raise ValueError("perceptual_duplicate only supports action='drop'")

    groups = parameter_table["perceptual_duplicate_group_id"].fillna("").astype(str)
    counts = (
        cast(pd.Series, pd.to_numeric(parameter_table["perceptual_duplicate_count"], errors="coerce"))
        .fillna(1)
        .astype(int)
    )
    distances = cast(pd.Series, pd.to_numeric(parameter_table["perceptual_duplicate_distance"], errors="coerce"))

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, distance in zip(groups.tolist(), counts.tolist(), distances.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"duplicate in group {group_id} distance {int(distance)}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "perceptual_duplicate_group_id": groups,
            "perceptual_duplicate_count": counts,
            "perceptual_duplicate_distance": distances,
            "perceptual_duplicate_action": actions,
            "perceptual_duplicate_reason": reasons,
        }
    )


def evaluate_semantic_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据语义重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("semantic_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action not in {"drop", "review"}:
        raise ValueError("semantic_duplicate only supports action='drop' or action='review'")

    groups = parameter_table["semantic_duplicate_group_id"].fillna("").astype(str)
    counts = (
        cast(pd.Series, pd.to_numeric(parameter_table["semantic_duplicate_count"], errors="coerce"))
        .fillna(1)
        .astype(int)
    )
    scores = cast(pd.Series, pd.to_numeric(parameter_table["semantic_duplicate_score"], errors="coerce"))
    nearest_ids = parameter_table["semantic_duplicate_nearest_image_id"].fillna("").astype(str)

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, score, nearest_id in zip(
        groups.tolist(),
        counts.tolist(),
        scores.tolist(),
        nearest_ids.tolist(),
        strict=True,
    ):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"semantic duplicate in group {group_id} score {float(score):.4f} nearest {nearest_id}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "semantic_duplicate_group_id": groups,
            "semantic_duplicate_count": counts,
            "semantic_duplicate_score": scores,
            "semantic_duplicate_nearest_image_id": nearest_ids,
            "semantic_duplicate_action": actions,
            "semantic_duplicate_reason": reasons,
        }
    )


def _score_threshold_frame(
    image_ids: pd.Series[Any],
    scores: pd.Series[Any],
    failed: pd.Series[bool],
    prefix: str,
    action: str,
    reason: str,
) -> pd.DataFrame:
    """构造分数阈值类算子的评估结果。"""
    return pd.DataFrame(
        {
            "image_id": image_ids,
            f"{prefix}_score": scores,
            f"{prefix}_action": failed.map(lambda value: action if value else "keep"),
            f"{prefix}_reason": failed.map(lambda value: reason if value else ""),
        }
    )


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")


def _as_float(value: object) -> float:
    """把配置值转换为 float。"""
    if isinstance(value, (str, bytes, int, float)):
        return float(value)
    raise TypeError(f"expected float-compatible config value, got {type(value).__name__}")


def _exposure_reason(
    dark: float,
    bright: float,
    clipped: float,
    max_dark: float,
    max_bright: float,
    max_clipped: float,
) -> str:
    """构造曝光检查命中的原因。"""
    reasons: list[str] = []
    if pd.notna(dark) and dark > max_dark:
        reasons.append(f"dark pixel ratio above {max_dark}")
    if pd.notna(bright) and bright > max_bright:
        reasons.append(f"bright pixel ratio above {max_bright}")
    if pd.notna(clipped) and clipped > max_clipped:
        reasons.append(f"clipped pixel ratio above {max_clipped}")
    return "; ".join(reasons)
