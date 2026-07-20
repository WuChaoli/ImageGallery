"""Compatibility helpers for dataset and dataset-view like inputs."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from typing import Any, cast

import pandas as pd
from PIL import Image

from image_gallery.dataset.fingerprint import dataframe_fingerprint


def read_dataset_frame(dataset: object, columns: list[str] | None = None) -> pd.DataFrame:
    """Read a dataframe from a dataset-like object with `to_frame` or `scan`."""
    typed_dataset = cast(Any, dataset)
    if hasattr(typed_dataset, "to_frame"):
        to_frame = cast(Callable[..., pd.DataFrame], typed_dataset.to_frame)
        if columns is None:
            return to_frame()
        return to_frame(columns)

    if not hasattr(typed_dataset, "scan"):
        raise TypeError("dataset must provide to_frame or scan")

    scan = cast(Callable[..., pd.DataFrame], typed_dataset.scan)
    if columns is None:
        return cast(pd.DataFrame, scan())

    for field_name in ("fields", "columns"):
        try:
            return scan(**{field_name: columns})
        except TypeError:
            continue

    raise TypeError("dataset.scan does not support fields/columns parameter")


def read_dataset_fingerprint(dataset: object, *, fallback_frame: pd.DataFrame | None = None) -> str:
    """Return dataset fingerprint in a backward compatible way."""
    typed_dataset = cast(Any, dataset)
    if hasattr(typed_dataset, "fingerprint"):
        return cast(Callable[[], str], typed_dataset.fingerprint)()
    frame = fallback_frame if fallback_frame is not None else read_dataset_frame(dataset)
    return dataframe_fingerprint(frame)


def normalize_identifier_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Map `asset_id` / `source_uri` to internal cleaning columns if absent."""
    normalized = frame.copy()
    if "image_id" not in normalized.columns and "asset_id" in normalized.columns:
        normalized["image_id"] = cast(pd.Series, normalized["asset_id"]).astype(str)
    if "image_uri" not in normalized.columns and "source_uri" in normalized.columns:
        normalized["image_uri"] = cast(pd.Series, normalized["source_uri"]).astype(str)
    return cast(pd.DataFrame, normalized)


def require_image_id(row: dict[str, object]) -> str:
    """Extract image identifier from a row dict."""
    if "image_id" in row:
        return str(row["image_id"])
    if "asset_id" in row:
        return str(row["asset_id"])
    raise KeyError("image_id (or asset_id) is required")


def row_image_uri(row: dict[str, object]) -> str:
    """Read image uri-like field from a row dict."""
    for key in ("image_uri", "source_uri"):
        if key in row:
            value = row[key]
            if isinstance(value, str):
                return value
    if "image_id" in row:
        return str(row["image_id"])
    if "asset_id" in row:
        return str(row["asset_id"])
    return ""


def read_dataset_image(dataset: object, image_id: str, image_uri: str) -> Image.Image:
    """Read decoded image from dataset-like object."""
    typed_dataset = cast(Any, dataset)
    if not hasattr(typed_dataset, "read_image"):
        raise AttributeError("dataset must provide read_image")
    read_image = cast(Callable[..., Image.Image], typed_dataset.read_image)
    try:
        return read_image(asset_id=image_id)
    except TypeError:
        return read_image(image_uri)


def _image_to_bytes(image: Image.Image) -> bytes:
    """Convert PIL image to bytes for operators relying on raw image bytes."""
    output = BytesIO()
    with image.copy() as converted:
        if converted.mode not in {"RGB", "RGBA", "L"}:
            converted = converted.convert("RGB")
        converted.save(output, format="PNG", optimize=False)
    return output.getvalue()


def read_dataset_image_bytes(dataset: object, image_id: str, image_uri: str) -> bytes:
    """Read image bytes from dataset-like object."""
    typed_dataset = cast(Any, dataset)
    if hasattr(typed_dataset, "read_image_bytes"):
        return cast(Callable[[str], bytes], typed_dataset.read_image_bytes)(image_uri)
    return _image_to_bytes(read_dataset_image(dataset, image_id, image_uri))
