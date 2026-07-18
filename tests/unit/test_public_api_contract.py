"""公开包导出与调用签名契约测试。"""

from __future__ import annotations

import hashlib
import importlib
import inspect

import pytest

EXPECTED_EXPORTS = {
    "image_gallery": ("__version__",),
    "image_gallery.annotations": ("LabelImgExporter", "LabelImgLoader"),
    "image_gallery.cleaning": (
        "ActionRange",
        "BasicCleaner",
        "Cleaner",
        "CleanerExecution",
        "CleanerRecipe",
        "CleanerResult",
        "DiskRunStore",
        "DryRunResult",
        "MemoryRunStore",
        "PreviewResult",
        "RunStore",
        "TemporaryRunStore",
        "evaluate_with_rules",
    ),
    "image_gallery.dataset": (
        "Dataset",
        "DatasetExporter",
        "DatasetExportResult",
        "DatasetImage",
        "DatasetImageBytesReadResult",
        "DatasetImageReadResult",
        "DatasetLoader",
        "TabularDatasetExporter",
    ),
    "image_gallery.dataset_manager": (
        "CommitResult",
        "ConflictError",
        "Dataset",
        "DatasetManager",
        "DatasetManagerError",
        "DatasetRepo",
        "DatasetSchema",
        "DatasetView",
        "EmbedResult",
        "NameConflictError",
        "ObjectNotFoundError",
        "RepoSchema",
        "StorageAuthorizationError",
        "TagDefinition",
        "ValidationError",
        "VectorField",
    ),
    "image_gallery.importers": (
        "DatasetParser",
        "ImportPipeline",
        "ImportResult",
        "LocalPathParser",
        "SourceParser",
        "SourceRecord",
        "UrlPathParser",
    ),
    "image_gallery.model_manager": (
        "ModelDefinition",
        "ModelManager",
        "ModelManagerError",
        "ModelRegistrationError",
        "ModelRuntime",
        "ModelRuntimeError",
    ),
    "image_gallery.operators": (
        "MetricSpec",
        "OperatorRegistry",
        "OperatorSpec",
        "create_default_metric_specs",
        "create_default_registry",
        "relative_to_absolute",
    ),
    "image_gallery.operators.computers": (
        "ExecutionMode",
        "DuplicateGroupComputer",
        "ImageBatch",
        "ImageBatchItem",
        "ImageBorderComputer",
        "ImageFormatDetailComputer",
        "ImageHashComputer",
        "ImageMetadataComputer",
        "ImageQualityComputer",
        "ImageQualityDetailComputer",
        "ParameterComputer",
        "ParameterRequest",
        "ParameterResult",
        "SemanticDuplicateGroupComputer",
        "SemanticEmbeddingComputer",
        "TableDerivedComputer",
    ),
    "image_gallery.schemas": ("RawDatasetSchema", "validate_raw_dataset"),
    "image_gallery.storage": ("FileSystemStorage", "MinioStorage", "Storage", "StorageBatchResult"),
    "image_gallery.storage_manager": (
        "ContentIntegrityError",
        "ObjectAlreadyExistsError",
        "ObjectNotFoundError",
        "PathSecurityError",
        "PrefixNotFoundError",
        "StorageManager",
        "StorageManagerError",
        "StoragePrefix",
        "StoredObject",
    ),
    "image_gallery.visualization": ("render_image_grid", "show_image_grid"),
}

# 使用摘要避免在测试中复制冗长注解，同时逐符号报告签名漂移。
EXPECTED_SIGNATURE_DIGESTS = {
    "image_gallery.annotations.LabelImgExporter": "c45a9624829cb7e5",
    "image_gallery.annotations.LabelImgLoader": "1c6a48d2a1896a1c",
    "image_gallery.cleaning.ActionRange": "539026164d918c75",
    "image_gallery.cleaning.BasicCleaner": "46f797631784de6f",
    "image_gallery.cleaning.Cleaner": "2e38e77b22c314a4",
    "image_gallery.cleaning.CleanerExecution": "6d9ad172e859567a",
    "image_gallery.cleaning.CleanerRecipe": "dcd4b10e7f94d354",
    "image_gallery.cleaning.CleanerResult": "186cadce765ba57b",
    "image_gallery.cleaning.DiskRunStore": "106472e76535bc3f",
    "image_gallery.cleaning.DryRunResult": "fab748c426dc16a9",
    "image_gallery.cleaning.MemoryRunStore": "6d7a93dbe23711a4",
    "image_gallery.cleaning.PreviewResult": "b11e732bf9bde61b",
    "image_gallery.cleaning.RunStore": "312d003da69a6f75",
    "image_gallery.cleaning.TemporaryRunStore": "6d7a93dbe23711a4",
    "image_gallery.cleaning.evaluate_with_rules": "4a2a0801dd5495bd",
    "image_gallery.dataset.Dataset": "af325b31344e3f27",
    "image_gallery.dataset.DatasetExporter": "312d003da69a6f75",
    "image_gallery.dataset.DatasetExportResult": "ead0d1faa773a03d",
    "image_gallery.dataset.DatasetImage": "fd60dcedf0517147",
    "image_gallery.dataset.DatasetImageBytesReadResult": "90427bf29b4802f3",
    "image_gallery.dataset.DatasetImageReadResult": "895a516920fe7078",
    "image_gallery.dataset.DatasetLoader": "312d003da69a6f75",
    "image_gallery.dataset.TabularDatasetExporter": "bb734c9777dd39a9",
    "image_gallery.dataset_manager.CommitResult": "eaf7c422c3aa6b50",
    "image_gallery.dataset_manager.Dataset": "1c6270ab231126d2",
    "image_gallery.dataset_manager.DatasetManager": "044784aee81d9a08",
    "image_gallery.dataset_manager.DatasetRepo": "21d2debefb597730",
    "image_gallery.dataset_manager.DatasetSchema": "1f1f83b9debf8261",
    "image_gallery.dataset_manager.DatasetView": "0c42e8c36d6db0a5",
    "image_gallery.dataset_manager.EmbedResult": "57c18534670f8670",
    "image_gallery.dataset_manager.RepoSchema": "bd3c938896d62596",
    "image_gallery.dataset_manager.TagDefinition": "a471504d18621052",
    "image_gallery.dataset_manager.VectorField": "a1e80f5f9d380506",
    "image_gallery.importers.DatasetParser": "4dbecb1da97eae26",
    "image_gallery.importers.ImportPipeline": "4bc87ae9f4637436",
    "image_gallery.importers.ImportResult": "07a1885a944eeb9f",
    "image_gallery.importers.LocalPathParser": "782a0ad31756b278",
    "image_gallery.importers.SourceParser": "312d003da69a6f75",
    "image_gallery.importers.SourceRecord": "2ef4553d44ceebe0",
    "image_gallery.importers.UrlPathParser": "62335e72527ba49b",
    "image_gallery.model_manager.ModelDefinition": "1d52644e91361152",
    "image_gallery.model_manager.ModelManager": "bd3fa0bde91c9929",
    "image_gallery.model_manager.ModelRuntime": "312d003da69a6f75",
    "image_gallery.operators.MetricSpec": "9a116ba49c15e668",
    "image_gallery.operators.OperatorRegistry": "6256b1e26a387179",
    "image_gallery.operators.OperatorSpec": "ed846332ae7de2d4",
    "image_gallery.operators.create_default_metric_specs": "b2eead90d49c11ba",
    "image_gallery.operators.create_default_registry": "3497472e71f737f0",
    "image_gallery.operators.relative_to_absolute": "252433cb423e4822",
    "image_gallery.operators.computers.ExecutionMode": "dad7a569fc881f0d",
    "image_gallery.operators.computers.DuplicateGroupComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageBatch": "579d087498fd8621",
    "image_gallery.operators.computers.ImageBatchItem": "38395039aa75149e",
    "image_gallery.operators.computers.ImageBorderComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageFormatDetailComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageHashComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageMetadataComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageQualityComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ImageQualityDetailComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ParameterComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.ParameterRequest": "db99dfc12dc5e3ad",
    "image_gallery.operators.computers.ParameterResult": "2ec3d7322257dbd0",
    "image_gallery.operators.computers.SemanticDuplicateGroupComputer": "2e38e77b22c314a4",
    "image_gallery.operators.computers.SemanticEmbeddingComputer": "b104c2640be8472b",
    "image_gallery.operators.computers.TableDerivedComputer": "2e38e77b22c314a4",
    "image_gallery.schemas.RawDatasetSchema": "a90d7a1fdb8cde95",
    "image_gallery.schemas.validate_raw_dataset": "222b5f6d8d2767da",
    "image_gallery.storage.FileSystemStorage": "d1242f89acbf014a",
    "image_gallery.storage.MinioStorage": "f0215f336d01b223",
    "image_gallery.storage.Storage": "2e38e77b22c314a4",
    "image_gallery.storage.StorageBatchResult": "7fecd65ef6036dc3",
    "image_gallery.storage_manager.StorageManager": "e60c9aa63675afb6",
    "image_gallery.storage_manager.StoragePrefix": "2c31cf003c86dc0e",
    "image_gallery.storage_manager.StoredObject": "8affcd0f6cf20803",
    "image_gallery.visualization.render_image_grid": "04e20dd69b64dc85",
    "image_gallery.visualization.show_image_grid": "19b46d236d5ffd16",
}


@pytest.mark.parametrize(("module_name", "expected"), EXPECTED_EXPORTS.items())
def test_public_exports_resolve(module_name: str, expected: tuple[str, ...]) -> None:
    module = importlib.import_module(module_name)

    assert tuple(module.__all__) == expected
    for name in expected:
        assert getattr(module, name) is not None


def test_public_callable_signatures_match() -> None:
    for symbol, expected_digest in EXPECTED_SIGNATURE_DIGESTS.items():
        module_name, name = symbol.rsplit(".", maxsplit=1)
        public_object = getattr(importlib.import_module(module_name), name)
        signature = str(inspect.signature(public_object))
        actual_digest = hashlib.sha256(signature.encode()).hexdigest()[:16]

        assert actual_digest == expected_digest, f"{symbol} signature drifted: {signature}"


def test_cleaning_unknown_export_raises_attribute_error() -> None:
    cleaning = importlib.import_module("image_gallery.cleaning")

    with pytest.raises(AttributeError, match="not_a_public_export"):
        assert cleaning.not_a_public_export is not None
