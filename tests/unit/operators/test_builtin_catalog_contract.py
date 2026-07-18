import hashlib
import inspect
import json
from copy import deepcopy
from dataclasses import asdict, fields, is_dataclass
from typing import cast

import pandas as pd
import pytest

from image_gallery import operators
from image_gallery.operators import builtin
from image_gallery.operators._builtin_metrics import create_builtin_metric_specs
from image_gallery.operators._builtin_specs import create_builtin_operator_specs
from image_gallery.operators.builtin import create_default_metric_specs, create_default_registry
from image_gallery.operators.computers.base import ParameterRequest
from image_gallery.operators.computers.semantic import SemanticEmbeddingComputer
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _operator_contract() -> list[dict[str, object]]:
    contract: list[dict[str, object]] = []
    for spec in create_default_registry().list_operator_specs():
        fields = cast(dict[str, object], asdict(spec))
        fields["evaluator"] = spec.evaluator.__name__
        contract.append(fields)
    return contract


def _metric_contract() -> dict[str, dict[str, object]]:
    return {name: cast(dict[str, object], asdict(spec)) for name, spec in create_default_metric_specs().items()}


def _computer_contract() -> list[dict[str, object]]:
    return [
        {
            "name": computer.name,
            "execution_mode": str(computer.execution_mode),
            "required_parameters": sorted(computer.required_parameters),
            "produced_parameters": sorted(computer.produced_parameters),
        }
        for computer in create_default_registry().list_parameter_computers()
    ]


def _mutable_object_ids(value: object) -> set[int]:
    if isinstance(value, dict):
        nested_ids = {id(value)}
        for nested_value in value.values():
            nested_ids.update(_mutable_object_ids(nested_value))
        return nested_ids
    if isinstance(value, list):
        nested_ids = {id(value)}
        for nested_value in value:
            nested_ids.update(_mutable_object_ids(nested_value))
        return nested_ids
    if is_dataclass(value) and not isinstance(value, type):
        nested_ids: set[int] = set()
        for data_field in fields(value):
            nested_ids.update(_mutable_object_ids(getattr(value, data_field.name)))
        return nested_ids
    return set()


def _mutate_nested_objects(value: object) -> None:
    if isinstance(value, dict):
        for nested_value in list(value.values()):
            _mutate_nested_objects(nested_value)
        value["__mutation_probe__"] = True
    elif isinstance(value, list):
        for nested_value in list(value):
            _mutate_nested_objects(nested_value)
        value.append("__mutation_probe__")
    elif is_dataclass(value) and not isinstance(value, type):
        for data_field in fields(value):
            _mutate_nested_objects(getattr(value, data_field.name))


def test_default_catalog_matches_characterized_operator_contract() -> None:
    assert _digest(_operator_contract()) == "6b69110c6ceb602ed2968dda80bb73aa2623cbfa274391b69b670112bf729e1a"


def test_operator_public_exports_and_factory_signatures_are_unchanged() -> None:
    assert operators.__all__ == [
        "MetricSpec",
        "OperatorRegistry",
        "OperatorSpec",
        "create_default_metric_specs",
        "create_default_registry",
        "relative_to_absolute",
    ]
    assert str(inspect.signature(create_default_registry)) == (
        "(semantic_providers: 'dict[str, SemanticEmbeddingProvider] | None' = None) -> 'OperatorRegistry'"
    )
    assert str(inspect.signature(create_default_metric_specs)) == "() -> 'dict[str, MetricSpec]'"


def test_default_catalog_matches_characterized_metric_contract() -> None:
    assert _digest(_metric_contract()) == "9b67f47cd98d3534ab9623416351e86b9bf932716ce2ac4ca030a2d967cd2205"


def test_default_registry_matches_characterized_computer_contract() -> None:
    assert _digest(_computer_contract()) == "08a5de2177195ae2f03db66e3b4e72d380b6c4e4d59a2690cb493bbad0b41357"


def test_private_catalog_builders_match_public_factories() -> None:
    registry_specs = create_default_registry().list_operator_specs()

    assert create_builtin_operator_specs() == registry_specs
    assert create_builtin_metric_specs() == create_default_metric_specs()


def test_builtin_module_keeps_evaluator_compatibility_imports() -> None:
    evaluator_names = {spec.evaluator.__name__ for spec in create_default_registry().list_operator_specs()}

    assert {getattr(builtin, name).__name__ for name in evaluator_names} == evaluator_names


def test_default_factories_return_independent_mutable_objects() -> None:
    first_registry = create_default_registry()
    second_registry = create_default_registry()
    first_specs = {spec.name: spec for spec in first_registry.list_operator_specs()}
    second_specs = {spec.name: spec for spec in second_registry.list_operator_specs()}

    assert len(first_specs) == len(second_specs) == 17
    assert first_specs.keys() == second_specs.keys()
    for operator_name, first_spec in first_specs.items():
        second_spec = second_specs[operator_name]
        second_snapshot = deepcopy(asdict(second_spec))

        assert first_spec is not second_spec
        assert first_spec.default_config is not second_spec.default_config
        assert first_spec.preview_policy is not second_spec.preview_policy
        assert _mutable_object_ids(first_spec.default_config).isdisjoint(
            _mutable_object_ids(second_spec.default_config)
        ), f"{operator_name} default_config shares nested mutable objects"
        assert _mutable_object_ids(first_spec.preview_policy).isdisjoint(
            _mutable_object_ids(second_spec.preview_policy)
        ), f"{operator_name} preview_policy shares nested mutable objects"

        _mutate_nested_objects(first_spec.default_config)
        _mutate_nested_objects(first_spec.preview_policy)
        assert asdict(second_spec) == second_snapshot

    first_metrics = create_default_metric_specs()
    second_metrics = create_default_metric_specs()
    assert first_metrics is not second_metrics
    assert first_metrics["blur"] is not second_metrics["blur"]


def test_default_registry_preserves_semantic_provider_mapping() -> None:
    provider = cast(SemanticEmbeddingProvider, object())
    providers = {"custom": provider}

    computer = create_default_registry(providers).get_parameter_computer("semantic_embedding_computer")

    assert isinstance(computer, SemanticEmbeddingComputer)
    assert computer._providers is providers


def test_megapixel_catalog_preserves_optional_maximum_threshold() -> None:
    frame = pd.DataFrame({"image_id": ["ok", "large"], "megapixels": [0.5, 2.0]})

    result = (
        create_default_registry()
        .get_operator("megapixel")
        .evaluate(
            frame,
            {"min_megapixels": 0.01, "max_megapixels": 1.0, "action": "review"},
        )
    )

    assert result["megapixel_action"].tolist() == ["keep", "review"]


@pytest.mark.parametrize(
    ("operator_name", "frame", "config", "message"),
    [
        (
            "exact_duplicate",
            pd.DataFrame(
                {
                    "image_id": ["image"],
                    "exact_duplicate_group_id": ["group"],
                    "exact_duplicate_count": [2],
                }
            ),
            {"keep": "last"},
            "exact_duplicate only supports keep='first'",
        ),
        (
            "perceptual_duplicate",
            pd.DataFrame(
                {
                    "image_id": ["image"],
                    "perceptual_duplicate_group_id": ["group"],
                    "perceptual_duplicate_count": [2],
                    "perceptual_duplicate_distance": [1],
                }
            ),
            {"keep": "last"},
            "perceptual_duplicate only supports keep='first'",
        ),
        (
            "perceptual_duplicate",
            pd.DataFrame(
                {
                    "image_id": ["image"],
                    "perceptual_duplicate_group_id": ["group"],
                    "perceptual_duplicate_count": [2],
                    "perceptual_duplicate_distance": [1],
                }
            ),
            {"action": "review"},
            "perceptual_duplicate only supports action='drop'",
        ),
        (
            "semantic_duplicate",
            pd.DataFrame(
                {
                    "image_id": ["image"],
                    "semantic_duplicate_group_id": ["group"],
                    "semantic_duplicate_count": [2],
                    "semantic_duplicate_score": [0.95],
                    "semantic_duplicate_nearest_image_id": ["other"],
                }
            ),
            {"keep": "last"},
            "semantic_duplicate only supports keep='first'",
        ),
        (
            "semantic_duplicate",
            pd.DataFrame(
                {
                    "image_id": ["image"],
                    "semantic_duplicate_group_id": ["group"],
                    "semantic_duplicate_count": [2],
                    "semantic_duplicate_score": [0.95],
                    "semantic_duplicate_nearest_image_id": ["other"],
                }
            ),
            {"action": "keep"},
            "semantic_duplicate only supports action='drop' or action='review'",
        ),
    ],
)
def test_duplicate_catalog_preserves_invalid_config_errors(
    operator_name: str,
    frame: pd.DataFrame,
    config: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_default_registry().get_operator(operator_name).evaluate(frame, config)


@pytest.mark.parametrize(
    ("operator_name", "frame", "config", "message"),
    [
        (
            "dimension",
            pd.DataFrame({"image_id": ["image"], "width": [1], "height": [1]}),
            {"min_width": object()},
            "expected int-compatible config value",
        ),
        (
            "blur",
            pd.DataFrame({"image_id": ["image"], "blur_score": [1.0]}),
            {"min_score": object()},
            "expected float-compatible config value",
        ),
    ],
)
def test_builtin_catalog_preserves_invalid_numeric_config_errors(
    operator_name: str,
    frame: pd.DataFrame,
    config: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        create_default_registry().get_operator(operator_name).evaluate(frame, config)


@pytest.mark.parametrize(
    ("computer_name", "message"),
    [
        ("image_metadata_computer", "ImageMetadataComputer requires image_batch"),
        ("image_format_detail_computer", "ImageFormatDetailComputer requires image_batch"),
        ("image_quality_computer", "ImageQualityComputer requires image_batch"),
        ("image_quality_detail_computer", "ImageQualityDetailComputer requires image_batch"),
        ("image_border_computer", "ImageBorderComputer requires image_batch"),
        ("image_hash_computer", "ImageHashComputer requires image_batch"),
        ("image_perceptual_hash_computer", "ImagePerceptualHashComputer requires image_batch"),
    ],
)
def test_default_per_image_computers_preserve_missing_batch_errors(
    computer_name: str,
    message: str,
    tmp_path,
) -> None:
    request = ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": []}),
        requested_parameters=frozenset(),
        config={},
        config_hash="default",
        artifacts_dir=tmp_path,
    )

    with pytest.raises(ValueError, match=message):
        create_default_registry().get_parameter_computer(computer_name).compute(request)
