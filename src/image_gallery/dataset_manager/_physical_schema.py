"""DatasetManager 物理 Schema DTO、类型转换与值规范化。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import count
from typing import TypeAlias, cast

import numpy as np
import pandas as pd
import pyarrow as pa
from pyiceberg.types import (
    BooleanType,
    DoubleType,
    IcebergType,
    IntegerType,
    ListType,
    LongType,
    NestedField,
    StringType,
    StructType,
)

from image_gallery.dataset_manager.errors import ValidationError

_PRIMITIVE_NAMES = {"boolean", "double", "integer", "long", "string"}
_INTEGER_MIN = -(2**31)
_INTEGER_MAX = 2**31 - 1
_LONG_MIN = -(2**63)
_LONG_MAX = 2**63 - 1


@dataclass(frozen=True, slots=True)
class PrimitiveFieldType:
    """描述 DatasetManager 支持的标量物理类型。"""

    name: str

    def __post_init__(self) -> None:
        if self.name not in _PRIMITIVE_NAMES:
            raise ValidationError(f"Unsupported Physical Schema type: {self.name}")


@dataclass(frozen=True, slots=True)
class StructField:
    """描述 Struct 中一个有序子字段。"""

    name: str
    field_type: FieldType | str
    required: bool = False

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValidationError("Struct field name cannot be empty")
        _require_bool(self.required, name="required")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "field_type", _normalize_field_type(self.field_type))


@dataclass(frozen=True, slots=True)
class StructFieldType:
    """描述名称唯一且顺序固定的 Struct 类型。"""

    fields: tuple[StructField, ...] | Sequence[StructField]

    def __post_init__(self) -> None:
        normalized = tuple(self.fields)
        if not normalized:
            raise ValidationError("Struct requires at least one field")
        if not all(isinstance(field, StructField) for field in normalized):
            raise ValidationError("Struct fields must use StructField")
        keys = [field.name.casefold() for field in normalized]
        if len(keys) != len(set(keys)):
            raise ValidationError("Struct field names must be case-insensitively unique")
        object.__setattr__(self, "fields", normalized)
        _validate_type_tree(self)


@dataclass(frozen=True, slots=True)
class ListFieldType:
    """描述元素类型固定的 List 类型。"""

    element_type: FieldType | str
    element_required: bool = False

    def __post_init__(self) -> None:
        _require_bool(self.element_required, name="element_required")
        object.__setattr__(self, "element_type", _normalize_field_type(self.element_type))
        _validate_type_tree(self)


FieldType: TypeAlias = PrimitiveFieldType | StructFieldType | ListFieldType


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """公开描述一个顶层物理列且不暴露 Iceberg field ID。"""

    name: str
    field_type: FieldType | str
    required: bool = False

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValidationError("Column name cannot be empty")
        _require_bool(self.required, name="required")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "field_type", _normalize_field_type(self.field_type))
        _validate_type_tree(cast(FieldType, self.field_type))

    def to_dict(self) -> dict[str, object]:
        """转换为稳定且不含 field ID 的 JSON-safe 字典。"""
        return {
            "name": self.name,
            "field_type": _field_type_to_dict(cast(FieldType, self.field_type)),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ColumnSpec:
        """从 JSON-safe 字典恢复列定义。"""
        _require_exact_keys(payload, {"name", "field_type", "required"}, path="column")
        name = payload["name"]
        required = payload["required"]
        field_type = payload["field_type"]
        if not isinstance(name, str) or not isinstance(required, bool) or not isinstance(field_type, Mapping):
            raise ValidationError("Invalid serialized ColumnSpec")
        return cls(
            name=name,
            field_type=_field_type_from_dict(cast(Mapping[str, object], field_type)),
            required=required,
        )


def column_spec_to_arrow(column: ColumnSpec) -> pa.Field:  # pyright: ignore[reportUnknownParameterType]
    """把公共列定义转换为 PyArrow Field。"""
    return pa.field(column.name, _field_type_to_arrow(cast(FieldType, column.field_type)), nullable=not column.required)


def column_spec_from_arrow(field: pa.Field) -> ColumnSpec:  # pyright: ignore[reportUnknownParameterType]
    """把 PyArrow Field 转换为公共列定义。"""
    return ColumnSpec(field.name, _field_type_from_arrow(field.type), required=not field.nullable)


def column_spec_to_iceberg(column: ColumnSpec) -> NestedField:  # pyright: ignore[reportUnknownParameterType]
    """把公共列定义转换为独立的 PyIceberg Field。"""
    ids = count(1)
    field_type = _field_type_to_iceberg(cast(FieldType, column.field_type), ids=ids)
    return NestedField(id=next(ids), name=column.name, type=field_type, required=column.required)


def column_spec_from_iceberg(field: NestedField) -> ColumnSpec:  # pyright: ignore[reportUnknownParameterType]
    """把 PyIceberg Field 转换为公共列定义并丢弃 field ID。"""
    return ColumnSpec(field.name, _field_type_from_iceberg(field.field_type), required=field.required)


def iceberg_type_for_addition(  # pyright: ignore[reportUnknownParameterType]
    field_type: FieldType | str,
) -> IcebergType:
    """生成供 UpdateSchema.add_column 递归重分配 ID 的 Iceberg 类型。"""
    return _field_type_to_iceberg(_normalize_field_type(field_type), ids=count(1))


def canonicalize_value(
    field_type: FieldType | str,
    value: object,
    *,
    required: bool,
    path: str,
) -> object:
    """按公开类型递归生成 JSON-safe canonical value。"""
    normalized_type = _normalize_field_type(field_type)
    if isinstance(value, np.generic):
        value = value.item()
    if _is_missing_scalar(value):
        if required:
            raise ValidationError(f"{path} is required")
        return None
    if isinstance(normalized_type, PrimitiveFieldType):
        return _canonicalize_primitive(normalized_type, value, path=path)
    if isinstance(normalized_type, ListFieldType):
        if not isinstance(value, list):
            raise ValidationError(f"{path} must be a list")
        return [
            canonicalize_value(
                normalized_type.element_type,
                element,
                required=normalized_type.element_required,
                path=f"{path}[{index}]",
            )
            for index, element in enumerate(value)
        ]
    if not isinstance(value, Mapping):
        raise ValidationError(f"{path} must be a mapping")
    string_keys = {key for key in value if isinstance(key, str)}
    if len(string_keys) != len(value):
        raise ValidationError(f"{path} field names must be strings")
    expected = {field.name for field in normalized_type.fields}
    unknown = string_keys - expected
    if unknown:
        raise ValidationError(f"{path} contains unknown fields: {sorted(unknown)}")
    result: dict[str, object] = {}
    for field in normalized_type.fields:
        child = value[field.name] if field.name in value else None
        result[field.name] = canonicalize_value(
            field.field_type,
            child,
            required=field.required,
            path=f"{path}.{field.name}",
        )
    return result


def _require_bool(value: object, *, name: str) -> None:
    if not isinstance(value, bool):
        raise ValidationError(f"{name} must be bool")


def _normalize_field_type(field_type: FieldType | str) -> FieldType:
    if isinstance(field_type, str):
        return PrimitiveFieldType(field_type)
    if isinstance(field_type, PrimitiveFieldType | StructFieldType | ListFieldType):
        return field_type
    raise ValidationError("Invalid Physical Schema field type")


def _validate_type_tree(field_type: FieldType, *, ancestors: frozenset[int] = frozenset()) -> None:
    identity = id(field_type)
    if identity in ancestors:
        raise ValidationError("Physical Schema type tree must be finite and acyclic")
    next_ancestors = ancestors | {identity}
    if isinstance(field_type, ListFieldType):
        _validate_type_tree(cast(FieldType, field_type.element_type), ancestors=next_ancestors)
    elif isinstance(field_type, StructFieldType):
        for field in field_type.fields:
            _validate_type_tree(cast(FieldType, field.field_type), ancestors=next_ancestors)


def _field_type_to_dict(field_type: FieldType) -> dict[str, object]:
    if isinstance(field_type, PrimitiveFieldType):
        return {"kind": "primitive", "name": field_type.name}
    if isinstance(field_type, ListFieldType):
        return {
            "kind": "list",
            "element_type": _field_type_to_dict(cast(FieldType, field_type.element_type)),
            "element_required": field_type.element_required,
        }
    return {
        "kind": "struct",
        "fields": [
            {
                "name": field.name,
                "field_type": _field_type_to_dict(cast(FieldType, field.field_type)),
                "required": field.required,
            }
            for field in field_type.fields
        ],
    }


def _field_type_from_dict(payload: Mapping[str, object]) -> FieldType:
    kind = payload.get("kind")
    if kind == "primitive":
        _require_exact_keys(payload, {"kind", "name"}, path="primitive")
        name = payload["name"]
        if not isinstance(name, str):
            raise ValidationError("Invalid serialized primitive type")
        return PrimitiveFieldType(name)
    if kind == "list":
        _require_exact_keys(payload, {"kind", "element_type", "element_required"}, path="list")
        element_type = payload["element_type"]
        element_required = payload["element_required"]
        if not isinstance(element_type, Mapping) or not isinstance(element_required, bool):
            raise ValidationError("Invalid serialized list type")
        return ListFieldType(
            _field_type_from_dict(cast(Mapping[str, object], element_type)),
            element_required=element_required,
        )
    if kind != "struct":
        raise ValidationError("Unknown serialized field type")
    _require_exact_keys(payload, {"kind", "fields"}, path="struct")
    fields = payload["fields"]
    if not isinstance(fields, list):
        raise ValidationError("Invalid serialized struct type")
    normalized_fields: list[StructField] = []
    for item in fields:
        if not isinstance(item, Mapping):
            raise ValidationError("Invalid serialized struct field")
        item_mapping = cast(Mapping[str, object], item)
        _require_exact_keys(item_mapping, {"name", "field_type", "required"}, path="struct field")
        name = item_mapping["name"]
        nested = item_mapping["field_type"]
        required = item_mapping["required"]
        if not isinstance(name, str) or not isinstance(nested, Mapping) or not isinstance(required, bool):
            raise ValidationError("Invalid serialized struct field")
        normalized_fields.append(
            StructField(name, _field_type_from_dict(cast(Mapping[str, object], nested)), required=required)
        )
    return StructFieldType(tuple(normalized_fields))


def _require_exact_keys(payload: Mapping[str, object], expected: set[str], *, path: str) -> None:
    if set(payload) != expected:
        raise ValidationError(f"Invalid serialized {path}")


def _field_type_to_arrow(field_type: FieldType) -> pa.DataType:  # pyright: ignore[reportUnknownParameterType]
    if isinstance(field_type, PrimitiveFieldType):
        return {
            "boolean": pa.bool_(),
            "double": pa.float64(),
            "integer": pa.int32(),
            "long": pa.int64(),
            "string": pa.string(),
        }[field_type.name]
    if isinstance(field_type, ListFieldType):
        element = pa.field(
            "element",
            _field_type_to_arrow(cast(FieldType, field_type.element_type)),
            nullable=not field_type.element_required,
        )
        return pa.list_(element)
    return pa.struct(
        [
            pa.field(
                field.name,
                _field_type_to_arrow(cast(FieldType, field.field_type)),
                nullable=not field.required,
            )
            for field in field_type.fields
        ]
    )


def _field_type_from_arrow(field_type: pa.DataType) -> FieldType:  # pyright: ignore[reportUnknownParameterType]
    if pa.types.is_boolean(field_type):
        return PrimitiveFieldType("boolean")
    if pa.types.is_float64(field_type):
        return PrimitiveFieldType("double")
    if pa.types.is_int32(field_type):
        return PrimitiveFieldType("integer")
    if pa.types.is_int64(field_type):
        return PrimitiveFieldType("long")
    if pa.types.is_string(field_type):
        return PrimitiveFieldType("string")
    if pa.types.is_list(field_type):
        list_type = cast(pa.ListType, field_type)
        return ListFieldType(
            _field_type_from_arrow(list_type.value_type),
            element_required=not list_type.value_field.nullable,
        )
    if pa.types.is_struct(field_type):
        struct_type = cast(pa.StructType, field_type)
        return StructFieldType(
            tuple(
                StructField(field.name, _field_type_from_arrow(field.type), required=not field.nullable)
                for field in struct_type
            )
        )
    raise ValidationError(f"Unsupported Arrow type: {field_type}")


def _field_type_to_iceberg(  # pyright: ignore[reportUnknownParameterType]
    field_type: FieldType,
    *,
    ids: count[int],
) -> IcebergType:
    if isinstance(field_type, PrimitiveFieldType):
        factories: dict[str, type[IcebergType]] = {
            "boolean": BooleanType,
            "double": DoubleType,
            "integer": IntegerType,
            "long": LongType,
            "string": StringType,
        }
        return factories[field_type.name]()
    if isinstance(field_type, ListFieldType):
        element_id = next(ids)
        element_type = _field_type_to_iceberg(cast(FieldType, field_type.element_type), ids=ids)
        return ListType(element_id, element_type, element_required=field_type.element_required)
    fields = []
    for field in field_type.fields:
        field_id = next(ids)
        nested_type = _field_type_to_iceberg(cast(FieldType, field.field_type), ids=ids)
        fields.append(NestedField(id=field_id, name=field.name, type=nested_type, required=field.required))
    return StructType(*fields)


def _field_type_from_iceberg(field_type: IcebergType) -> FieldType:  # pyright: ignore[reportUnknownParameterType]
    if isinstance(field_type, BooleanType):
        return PrimitiveFieldType("boolean")
    if isinstance(field_type, DoubleType):
        return PrimitiveFieldType("double")
    if isinstance(field_type, IntegerType):
        return PrimitiveFieldType("integer")
    if isinstance(field_type, LongType):
        return PrimitiveFieldType("long")
    if isinstance(field_type, StringType):
        return PrimitiveFieldType("string")
    if isinstance(field_type, ListType):
        return ListFieldType(
            _field_type_from_iceberg(field_type.element_type),
            element_required=field_type.element_required,
        )
    if isinstance(field_type, StructType):
        return StructFieldType(
            tuple(
                StructField(
                    field.name,
                    _field_type_from_iceberg(field.field_type),
                    required=field.required,
                )
                for field in field_type.fields
            )
        )
    raise ValidationError(f"Unsupported Iceberg type: {field_type}")


def _is_missing_scalar(value: object) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value))


def _canonicalize_primitive(field_type: PrimitiveFieldType, value: object, *, path: str) -> object:
    if field_type.name == "string":
        if not isinstance(value, str):
            raise ValidationError(f"{path} must be a string")
        return value
    if field_type.name == "boolean":
        if not isinstance(value, bool):
            raise ValidationError(f"{path} must be a boolean")
        return value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{path} must be numeric")
    if field_type.name == "double":
        return float(value)
    if not isinstance(value, int):
        raise ValidationError(f"{path} must be an integer")
    minimum, maximum = (_INTEGER_MIN, _INTEGER_MAX) if field_type.name == "integer" else (_LONG_MIN, _LONG_MAX)
    if value < minimum or value > maximum:
        raise ValidationError(f"{path} is outside {field_type.name} range")
    return value
