"""公开包导出与调用签名契约测试。"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import types
import typing
from enum import Enum

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
        "ColumnSpec",
        "CommitResult",
        "ConflictError",
        "Dataset",
        "DatasetManager",
        "DatasetManagerError",
        "DatasetRepo",
        "DatasetSchema",
        "DatasetView",
        "EmbedResult",
        "ListFieldType",
        "NameConflictError",
        "ObjectNotFoundError",
        "PrimitiveFieldType",
        "RepoSchema",
        "StorageAuthorizationError",
        "StructField",
        "StructFieldType",
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

EXPECTED_CLEANING_TARGETS = {
    "ActionRange": "image_gallery.cleaning.action_range.ActionRange",
    "BasicCleaner": "image_gallery.cleaning.basic.BasicCleaner",
    "Cleaner": "image_gallery.cleaning.cleaner.Cleaner",
    "CleanerExecution": "image_gallery.cleaning.execution.CleanerExecution",
    "CleanerRecipe": "image_gallery.cleaning.recipe.CleanerRecipe",
    "CleanerResult": "image_gallery.cleaning.result.CleanerResult",
    "DiskRunStore": "image_gallery.cleaning.run_store.DiskRunStore",
    "DryRunResult": "image_gallery.cleaning.execution.DryRunResult",
    "MemoryRunStore": "image_gallery.cleaning.run_store.MemoryRunStore",
    "PreviewResult": "image_gallery.cleaning.preview.PreviewResult",
    "RunStore": "image_gallery.cleaning.run_store.RunStore",
    "TemporaryRunStore": "image_gallery.cleaning.run_store.TemporaryRunStore",
    "evaluate_with_rules": "image_gallery.cleaning.rule_evaluator.evaluate_with_rules",
}

EXPECTED_ENUM_VALUES = {
    "image_gallery.operators.computers.ExecutionMode": (
        ("PER_IMAGE", "per_image"),
        ("TABLE", "table"),
        ("DATASET_AGGREGATE", "dataset_aggregate"),
    ),
}

# 使用摘要避免在测试中复制冗长注解，同时逐符号报告签名漂移。
EXPECTED_SIGNATURE_DIGESTS = {
    "image_gallery.annotations.LabelImgExporter": "db3019c01473f4f8",
    "image_gallery.annotations.LabelImgLoader": "5e262d9915e1b6c7",
    "image_gallery.cleaning.ActionRange": "a4b3e46a9333a8ee",
    "image_gallery.cleaning.BasicCleaner": "e36cde8e1f686b2c",
    "image_gallery.cleaning.Cleaner": "29b2d070f1ef36cf",
    "image_gallery.cleaning.CleanerExecution": "4cc13fd37d1997eb",
    "image_gallery.cleaning.CleanerRecipe": "e68f1da23f2cc6b1",
    "image_gallery.cleaning.CleanerResult": "974587c6db0d42db",
    "image_gallery.cleaning.DiskRunStore": "48640df07abf157b",
    "image_gallery.cleaning.DryRunResult": "da48f87b4dcda9cc",
    "image_gallery.cleaning.MemoryRunStore": "56fcb468afb2ec45",
    "image_gallery.cleaning.PreviewResult": "f9f51b4f90771fcf",
    "image_gallery.cleaning.RunStore": "592095f8a9cafdd7",
    "image_gallery.cleaning.TemporaryRunStore": "56fcb468afb2ec45",
    "image_gallery.cleaning.evaluate_with_rules": "7fbc6d96776b2e41",
    "image_gallery.dataset.Dataset": "b5ab90ec42208b07",
    "image_gallery.dataset.DatasetExporter": "592095f8a9cafdd7",
    "image_gallery.dataset.DatasetExportResult": "efbf9f20e558e498",
    "image_gallery.dataset.DatasetImage": "0c8825ac816cca27",
    "image_gallery.dataset.DatasetImageBytesReadResult": "779c7f39dee36488",
    "image_gallery.dataset.DatasetImageReadResult": "8610959283e914e6",
    "image_gallery.dataset.DatasetLoader": "592095f8a9cafdd7",
    "image_gallery.dataset.TabularDatasetExporter": "a4be4929521128b4",
    "image_gallery.dataset_manager.ColumnSpec": "dbc957fb647294b8",
    "image_gallery.dataset_manager.CommitResult": "9918e046956943f6",
    "image_gallery.dataset_manager.Dataset": "d19bf4b400d291d6",
    "image_gallery.dataset_manager.DatasetManager": "483b454e50a64066",
    "image_gallery.dataset_manager.DatasetRepo": "eb76f404ce57d321",
    "image_gallery.dataset_manager.DatasetSchema": "8fcd810ef3118bd2",
    "image_gallery.dataset_manager.DatasetView": "52d2e8e9b615f0ee",
    "image_gallery.dataset_manager.EmbedResult": "02acf368a3f0aa0a",
    "image_gallery.dataset_manager.ListFieldType": "8dcd7d5d80859fce",
    "image_gallery.dataset_manager.PrimitiveFieldType": "7df33d2352539893",
    "image_gallery.dataset_manager.RepoSchema": "32fbc9512982f301",
    "image_gallery.dataset_manager.TagDefinition": "2c2832ae65f1739e",
    "image_gallery.dataset_manager.StructField": "dbc957fb647294b8",
    "image_gallery.dataset_manager.StructFieldType": "cc3b27448fec0304",
    "image_gallery.dataset_manager.VectorField": "1ffa41ca88a3668f",
    "image_gallery.importers.DatasetParser": "3735b220ccdec87e",
    "image_gallery.importers.ImportPipeline": "0a23e0d0670fda2a",
    "image_gallery.importers.ImportResult": "d6eeb45f41117fe7",
    "image_gallery.importers.LocalPathParser": "1963b612a6d14db5",
    "image_gallery.importers.SourceParser": "592095f8a9cafdd7",
    "image_gallery.importers.SourceRecord": "c60f17b109ba07b7",
    "image_gallery.importers.UrlPathParser": "c2ddc893264d616e",
    "image_gallery.model_manager.ModelDefinition": "2dd2afacdb002262",
    "image_gallery.model_manager.ModelManager": "587becf628fc548a",
    "image_gallery.model_manager.ModelRuntime": "592095f8a9cafdd7",
    "image_gallery.operators.MetricSpec": "a14722d3d9133271",
    "image_gallery.operators.OperatorRegistry": "56fcb468afb2ec45",
    "image_gallery.operators.OperatorSpec": "c70dc9e9acbec11c",
    "image_gallery.operators.create_default_metric_specs": "7da0e28420db0da9",
    "image_gallery.operators.create_default_registry": "9233b9194444ffea",
    "image_gallery.operators.relative_to_absolute": "0f47a1f13f03a27f",
    "image_gallery.operators.computers.ExecutionMode": "3d57a046cd56e99b",
    "image_gallery.operators.computers.DuplicateGroupComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageBatch": "9c7af568aaff45e3",
    "image_gallery.operators.computers.ImageBatchItem": "edec8408fd04c98a",
    "image_gallery.operators.computers.ImageBorderComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageFormatDetailComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageHashComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageMetadataComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageQualityComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ImageQualityDetailComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ParameterComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.ParameterRequest": "fb1563c6b98694fb",
    "image_gallery.operators.computers.ParameterResult": "25f1ab5114e6c720",
    "image_gallery.operators.computers.SemanticDuplicateGroupComputer": "29b2d070f1ef36cf",
    "image_gallery.operators.computers.SemanticEmbeddingComputer": "5b158a8a2942e4dd",
    "image_gallery.operators.computers.TableDerivedComputer": "29b2d070f1ef36cf",
    "image_gallery.schemas.RawDatasetSchema": "4bab0d6d68e07a13",
    "image_gallery.schemas.validate_raw_dataset": "573d6b5618c4505d",
    "image_gallery.storage.FileSystemStorage": "99a9c037f299994b",
    "image_gallery.storage.MinioStorage": "346c4f23e371f33c",
    "image_gallery.storage.Storage": "29b2d070f1ef36cf",
    "image_gallery.storage.StorageBatchResult": "653885ffd39cdb5c",
    "image_gallery.storage_manager.StorageManager": "a10b277142eca62e",
    "image_gallery.storage_manager.StoragePrefix": "8472335770a442c6",
    "image_gallery.storage_manager.StoredObject": "6f596d71bd0bef7b",
    "image_gallery.visualization.render_image_grid": "9862f10ef6231b22",
    "image_gallery.visualization.show_image_grid": "60c05003541e1874",
}


EXPECTED_METHOD_SIGNATURE_DIGESTS = {
    "image_gallery.dataset_manager.ColumnSpec.from_dict": "4fdc44de1dfdf6cc",
    "image_gallery.dataset_manager.ColumnSpec.to_dict": "e63f3c351b4af5d9",
    "image_gallery.annotations.LabelImgExporter.export": "1539f3b113a7562a",
    "image_gallery.annotations.LabelImgLoader.load": "4c10f82249332e6d",
    "image_gallery.cleaning.ActionRange.contains": "9cd9a43b55fbd014",
    "image_gallery.cleaning.ActionRange.from_string": "dd81e85886fcb0dc",
    "image_gallery.cleaning.BasicCleaner.compile": "94c43c568d0e5c78",
    "image_gallery.cleaning.BasicCleaner.config": "0636311981894836",
    "image_gallery.cleaning.BasicCleaner.export_config_template": "de718b9602b5e967",
    "image_gallery.cleaning.BasicCleaner.from_config": "6d641e30fbeaf247",
    "image_gallery.cleaning.BasicCleaner.from_recipe": "54ba3ee65ba082f8",
    "image_gallery.cleaning.BasicCleaner.from_toml": "5c22c2ab9b981a3b",
    "image_gallery.cleaning.BasicCleaner.plan": "3a06cfabf0d8a71c",
    "image_gallery.cleaning.BasicCleaner.run": "9b6f8569bb7cecce",
    "image_gallery.cleaning.Cleaner.compile": "4c10f82249332e6d",
    "image_gallery.cleaning.Cleaner.config": "39a01278d28fb844",
    "image_gallery.cleaning.Cleaner.plan": "1fc886da14350401",
    "image_gallery.cleaning.Cleaner.run": "7ba26a54869784ce",
    "image_gallery.cleaning.CleanerExecution.dry_run": "f3145d4ec3e9680e",
    "image_gallery.cleaning.CleanerExecution.plan": "3a06cfabf0d8a71c",
    "image_gallery.cleaning.CleanerExecution.rerun": "81ed6489532b234a",
    "image_gallery.cleaning.CleanerExecution.resume": "62ed6e2c26a1aa2b",
    "image_gallery.cleaning.CleanerExecution.run": "9b6f8569bb7cecce",
    "image_gallery.cleaning.CleanerRecipe.compile_selectors": "2fc1f776ee6042fd",
    "image_gallery.cleaning.CleanerRecipe.from_yaml": "736650aa4fc31d0f",
    "image_gallery.cleaning.CleanerResult.cleanup": "fe071fae7845cd07",
    "image_gallery.cleaning.CleanerResult.explain": "e2386121083bbf58",
    "image_gallery.cleaning.CleanerResult.export": "d6734c28095b778f",
    "image_gallery.cleaning.CleanerResult.export_debug_bundle": "929c5bdc9cffb718",
    "image_gallery.cleaning.CleanerResult.export_manifest": "86fac872d5300188",
    "image_gallery.cleaning.CleanerResult.export_relations": "e6af0b6cb8f5d414",
    "image_gallery.cleaning.CleanerResult.export_table": "86fac872d5300188",
    "image_gallery.cleaning.CleanerResult.preview": "a078b6fa1dff0daf",
    "image_gallery.cleaning.CleanerResult.preview_html": "3ea09b312a3ddd46",
    "image_gallery.cleaning.CleanerResult.result": "e35cb5a545f51a6c",
    "image_gallery.cleaning.CleanerResult.state": "3a06cfabf0d8a71c",
    "image_gallery.cleaning.CleanerResult.status": "6e752d5cbb5574b5",
    "image_gallery.cleaning.DiskRunStore.cleanup": "fe071fae7845cd07",
    "image_gallery.cleaning.DiskRunStore.materialize_dataset": "9ab644abff001850",
    "image_gallery.cleaning.DiskRunStore.read_json": "68632166480168ac",
    "image_gallery.cleaning.DiskRunStore.read_table": "68c888fcdac29890",
    "image_gallery.cleaning.DiskRunStore.run_dir": "4ffe849aae332074",
    "image_gallery.cleaning.DiskRunStore.write_json": "9230209870f84034",
    "image_gallery.cleaning.DiskRunStore.write_table": "29494b3129878f11",
    "image_gallery.cleaning.MemoryRunStore.cleanup": "fe071fae7845cd07",
    "image_gallery.cleaning.MemoryRunStore.materialize_dataset": "9ab644abff001850",
    "image_gallery.cleaning.MemoryRunStore.read_json": "68632166480168ac",
    "image_gallery.cleaning.MemoryRunStore.read_table": "68c888fcdac29890",
    "image_gallery.cleaning.MemoryRunStore.run_dir": "4ffe849aae332074",
    "image_gallery.cleaning.MemoryRunStore.write_json": "9230209870f84034",
    "image_gallery.cleaning.MemoryRunStore.write_table": "29494b3129878f11",
    "image_gallery.cleaning.RunStore.cleanup": "fe071fae7845cd07",
    "image_gallery.cleaning.RunStore.materialize_dataset": "9ab644abff001850",
    "image_gallery.cleaning.RunStore.read_json": "68632166480168ac",
    "image_gallery.cleaning.RunStore.read_table": "68c888fcdac29890",
    "image_gallery.cleaning.RunStore.run_dir": "4ffe849aae332074",
    "image_gallery.cleaning.RunStore.write_json": "9230209870f84034",
    "image_gallery.cleaning.RunStore.write_table": "29494b3129878f11",
    "image_gallery.cleaning.TemporaryRunStore.cleanup": "fe071fae7845cd07",
    "image_gallery.cleaning.TemporaryRunStore.materialize_dataset": "9ab644abff001850",
    "image_gallery.cleaning.TemporaryRunStore.read_json": "68632166480168ac",
    "image_gallery.cleaning.TemporaryRunStore.read_table": "68c888fcdac29890",
    "image_gallery.cleaning.TemporaryRunStore.run_dir": "4ffe849aae332074",
    "image_gallery.cleaning.TemporaryRunStore.write_json": "9230209870f84034",
    "image_gallery.cleaning.TemporaryRunStore.write_table": "29494b3129878f11",
    "image_gallery.dataset.Dataset.count": "7605b08c3a601697",
    "image_gallery.dataset.Dataset.draw": "6a59fef2feddb96c",
    "image_gallery.dataset.Dataset.export": "f124c79d962b6ca0",
    "image_gallery.dataset.Dataset.fingerprint": "6e752d5cbb5574b5",
    "image_gallery.dataset.Dataset.iter_images": "d0464f53eacf2732",
    "image_gallery.dataset.Dataset.load": "6044e89fb730799b",
    "image_gallery.dataset.Dataset.preview": "1a53b9c5891fea2d",
    "image_gallery.dataset.Dataset.read_image": "88058af2a7b6ed60",
    "image_gallery.dataset.Dataset.read_image_batch": "850f0116965e2237",
    "image_gallery.dataset.Dataset.read_image_bytes": "62ba350d86d02c3c",
    "image_gallery.dataset.Dataset.read_image_bytes_batch": "fd5aca83276ed3c2",
    "image_gallery.dataset.Dataset.scan": "87b670d0bd5e4b94",
    "image_gallery.dataset.Dataset.to_frame": "da901757dbd1c4c6",
    "image_gallery.dataset.Dataset.validate_readable": "fe071fae7845cd07",
    "image_gallery.dataset.Dataset.write": "339a9432e99bb3c0",
    "image_gallery.dataset.DatasetExporter.export": "d4464b51fe19510c",
    "image_gallery.dataset.DatasetImage.read_bytes": "31c11ce8c232e892",
    "image_gallery.dataset.DatasetImage.read_image": "915b736e63dc188f",
    "image_gallery.dataset.DatasetLoader.load": "59ee5974fa1419d1",
    "image_gallery.dataset.TabularDatasetExporter.export": "1539f3b113a7562a",
    "image_gallery.dataset_manager.Dataset.commit": "c127753773e7541b",
    "image_gallery.dataset_manager.Dataset.create_branch": "4a6b8c6c7fa9b475",
    "image_gallery.dataset_manager.Dataset.create_checkpoint": "4a6b8c6c7fa9b475",
    "image_gallery.dataset_manager.Dataset.generate_embed": "792d5e373448cb11",
    "image_gallery.dataset_manager.Dataset.list_checkpoints": "352a2c38e96e3139",
    "image_gallery.dataset_manager.Dataset.open_branch": "819f1ddeeca482eb",
    "image_gallery.dataset_manager.Dataset.open_checkpoint": "471467a731b0c477",
    "image_gallery.dataset_manager.Dataset.rollback": "1f200e1f458132cc",
    "image_gallery.dataset_manager.DatasetManager.close": "fe071fae7845cd07",
    "image_gallery.dataset_manager.DatasetManager.create_repo": "ec2b66931f7cf658",
    "image_gallery.dataset_manager.DatasetManager.list_repos": "59486bf5b3f2e7c6",
    "image_gallery.dataset_manager.DatasetManager.local": "51b5c6b1fc84bc97",
    "image_gallery.dataset_manager.DatasetManager.open_repo": "ec2b66931f7cf658",
    "image_gallery.dataset_manager.DatasetManager.postgres": "d312b0988cb4a3a5",
    "image_gallery.dataset_manager.DatasetManager.recover_operations": "7605b08c3a601697",
    "image_gallery.dataset_manager.DatasetRepo.archive_tag": "9ee6fa45951dd66b",
    "image_gallery.dataset_manager.DatasetRepo.bind_storage_prefix": "a0404b6d9ba5505c",
    "image_gallery.dataset_manager.DatasetRepo.clone_dataset": "63fa0db8a7ac2efb",
    "image_gallery.dataset_manager.DatasetRepo.create_dataset": "a20dc0064ba4e68e",
    "image_gallery.dataset_manager.DatasetRepo.create_tag": "946344bb7116bab6",
    "image_gallery.dataset_manager.DatasetRepo.get_vector_field": "5ed352508b5729a7",
    "image_gallery.dataset_manager.DatasetRepo.list_datasets": "53900b365a75a102",
    "image_gallery.dataset_manager.DatasetRepo.list_storage_prefix_ids": "352a2c38e96e3139",
    "image_gallery.dataset_manager.DatasetRepo.list_vector_fields": "93ef441e47c7a787",
    "image_gallery.dataset_manager.DatasetRepo.open_dataset": "a20dc0064ba4e68e",
    "image_gallery.dataset_manager.DatasetRepo.open_vector_field": "ac37411914d1070d",
    "image_gallery.dataset_manager.DatasetRepo.rename_tag": "5c0650feed4f27ff",
    "image_gallery.dataset_manager.DatasetSchema.add_column": "839367699aa83b09",
    "image_gallery.dataset_manager.DatasetSchema.get_column": "66d873f611251ae6",
    "image_gallery.dataset_manager.DatasetSchema.list_columns": "afbd6eb6846e72da",
    "image_gallery.dataset_manager.DatasetView.count": "7605b08c3a601697",
    "image_gallery.dataset_manager.DatasetView.get_row": "734a3253abf5f6ed",
    "image_gallery.dataset_manager.DatasetView.get_rows": "f2c04380c45218db",
    "image_gallery.dataset_manager.DatasetView.iter_images": "08003d273e94b8f2",
    "image_gallery.dataset_manager.DatasetView.preview": "7ecb10d176125629",
    "image_gallery.dataset_manager.DatasetView.read_image": "3bec7052c0d3a910",
    "image_gallery.dataset_manager.DatasetView.scan": "2f8640b543659f5f",
    "image_gallery.dataset_manager.DatasetView.verify_image": "16b436df2541de5a",
    "image_gallery.dataset_manager.RepoSchema.add_vector": "7a609a04cadc4912",
    "image_gallery.dataset_manager.RepoSchema.get_vector": "ac37411914d1070d",
    "image_gallery.dataset_manager.RepoSchema.list_vectors": "93ef441e47c7a787",
    "image_gallery.dataset_manager.VectorField.get": "a33cccfd5df0e509",
    "image_gallery.importers.DatasetParser.parse": "c654232cfb6618a3",
    "image_gallery.importers.ImportPipeline.run": "6d793b302dd2d2fb",
    "image_gallery.importers.LocalPathParser.parse": "c654232cfb6618a3",
    "image_gallery.importers.SourceParser.parse": "c654232cfb6618a3",
    "image_gallery.importers.UrlPathParser.parse": "c654232cfb6618a3",
    "image_gallery.model_manager.ModelManager.bind_engine": "bdb6fa17cdc1082d",
    "image_gallery.model_manager.ModelManager.close": "fe071fae7845cd07",
    "image_gallery.model_manager.ModelManager.embed": "a3b104b3426e4270",
    "image_gallery.model_manager.ModelManager.get": "2ba970781f66ac88",
    "image_gallery.model_manager.ModelManager.register": "11d43591253174ab",
    "image_gallery.model_manager.ModelRuntime.close": "fe071fae7845cd07",
    "image_gallery.model_manager.ModelRuntime.embed": "0a22e47a7ebdfbe5",
    "image_gallery.operators.OperatorRegistry.find_computers_for_parameters": "f7f6acbf13508077",
    "image_gallery.operators.OperatorRegistry.get_operator": "204d744d92cca411",
    "image_gallery.operators.OperatorRegistry.get_parameter_computer": "f7b5dd5a5b71af40",
    "image_gallery.operators.OperatorRegistry.get_parameter_producer": "0831bfd64d2836c8",
    "image_gallery.operators.OperatorRegistry.list_categories": "352a2c38e96e3139",
    "image_gallery.operators.OperatorRegistry.list_operator_specs": "d69bf27d5f71b6bb",
    "image_gallery.operators.OperatorRegistry.list_operators": "352a2c38e96e3139",
    "image_gallery.operators.OperatorRegistry.list_parameter_computers": "c1bee5486a3456b2",
    "image_gallery.operators.OperatorRegistry.register_operator": "7275324727f9a14b",
    "image_gallery.operators.OperatorRegistry.register_parameter_computer": "aa1f73e929566557",
    "image_gallery.operators.OperatorSpec.evaluate": "7f113470ed5a05de",
    "image_gallery.operators.computers.DuplicateGroupComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageBorderComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageFormatDetailComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageHashComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageMetadataComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageQualityComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ImageQualityDetailComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.ParameterComputer.before_run_check": "a5bc248788a281f8",
    "image_gallery.operators.computers.ParameterComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.SemanticDuplicateGroupComputer.before_run_check": "a5bc248788a281f8",
    "image_gallery.operators.computers.SemanticDuplicateGroupComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.SemanticEmbeddingComputer.before_run_check": "a5bc248788a281f8",
    "image_gallery.operators.computers.SemanticEmbeddingComputer.compute": "89c409da6dc93819",
    "image_gallery.operators.computers.TableDerivedComputer.compute": "89c409da6dc93819",
    "image_gallery.storage.FileSystemStorage.connect": "a5ec43950c4e4d5a",
    "image_gallery.storage.FileSystemStorage.contains_image_uri": "5b4055b414adf92e",
    "image_gallery.storage.FileSystemStorage.copy": "979ee9b63e193c28",
    "image_gallery.storage.FileSystemStorage.delete": "d8fcb92402be0c43",
    "image_gallery.storage.FileSystemStorage.exists": "a973336d7187c8f9",
    "image_gallery.storage.FileSystemStorage.make_image_uri": "6cbc23206552116f",
    "image_gallery.storage.FileSystemStorage.move": "979ee9b63e193c28",
    "image_gallery.storage.FileSystemStorage.validate_output_path": "278e685b6143cc4b",
    "image_gallery.storage.MinioStorage.connect": "adac6c6aa01d7161",
    "image_gallery.storage.MinioStorage.copy": "979ee9b63e193c28",
    "image_gallery.storage.MinioStorage.delete": "d8fcb92402be0c43",
    "image_gallery.storage.MinioStorage.exists": "a973336d7187c8f9",
    "image_gallery.storage.MinioStorage.make_image_uri": "6cbc23206552116f",
    "image_gallery.storage.MinioStorage.move": "979ee9b63e193c28",
    "image_gallery.storage.Storage.batch_read_bytes": "70ee34ea0b1a67fe",
    "image_gallery.storage.Storage.batch_write_bytes": "e79fb7bb96ba40c9",
    "image_gallery.storage.Storage.copy": "979ee9b63e193c28",
    "image_gallery.storage.Storage.delete": "d8fcb92402be0c43",
    "image_gallery.storage.Storage.delete_many": "70ee34ea0b1a67fe",
    "image_gallery.storage.Storage.exists": "a973336d7187c8f9",
    "image_gallery.storage.Storage.exists_many": "70ee34ea0b1a67fe",
    "image_gallery.storage.Storage.make_image_uri": "6cbc23206552116f",
    "image_gallery.storage.Storage.move": "979ee9b63e193c28",
    "image_gallery.storage.Storage.read_bytes": "25ffd0aaab8992ad",
    "image_gallery.storage.Storage.read_many": "70ee34ea0b1a67fe",
    "image_gallery.storage.Storage.write_bytes": "5db1561a3a43606b",
    "image_gallery.storage.Storage.write_many": "e79fb7bb96ba40c9",
    "image_gallery.storage_manager.StorageManager.close": "fe071fae7845cd07",
    "image_gallery.storage_manager.StorageManager.get_prefix": "ad95fa691b667e46",
    "image_gallery.storage_manager.StorageManager.read_bytes": "dd9d8dbbb12bd12f",
    "image_gallery.storage_manager.StorageManager.recover_managed": "6a0d58837980ed04",
    "image_gallery.storage_manager.StorageManager.register_file_prefix": "9266f298e66f5424",
    "image_gallery.storage_manager.StorageManager.register_s3_prefix": "b8f6c5252ac9a38c",
    "image_gallery.storage_manager.StorageManager.register_sftp_prefix": "246e1e421ba51772",
    "image_gallery.storage_manager.StorageManager.restore_prefix": "8c6001f199b20c2b",
    "image_gallery.storage_manager.StorageManager.verify": "0818660363b1645e",
    "image_gallery.storage_manager.StorageManager.verify_external": "14af84a4de4f22ed",
    "image_gallery.storage_manager.StorageManager.write_bytes": "ed679aac22cf3b05",
    "image_gallery.storage_manager.StorageManager.write_managed": "da26c2eb359c5480",
}


def _canonical_annotation(annotation: object) -> str:
    """将注解转换为跨 Python 小版本稳定的文本。"""
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        return annotation

    origin = typing.get_origin(annotation)
    arguments = typing.get_args(annotation)
    if origin in {typing.Union, types.UnionType}:
        return " | ".join(_canonical_annotation(argument) for argument in arguments)
    if origin is not None:
        origin_text = _canonical_annotation(origin)
        arguments_text = ", ".join(_canonical_annotation(argument) for argument in arguments)
        return f"{origin_text}[{arguments_text}]"

    module = getattr(annotation, "__module__", None)
    qualname = getattr(annotation, "__qualname__", None)
    if isinstance(module, str) and isinstance(qualname, str):
        return qualname if module == "builtins" else f"{module}.{qualname}"
    return repr(annotation).removeprefix("typing.")


def _canonical_default(default: object) -> str:
    """将默认值转换为稳定文本。"""
    if default is inspect.Signature.empty:
        return ""
    if default is None or isinstance(default, (bool, int, float, str, bytes)):
        return repr(default)
    return _canonical_annotation(type(default)) + ":" + repr(default)


def _canonical_signature(callable_object: object) -> str:
    """生成不依赖 inspect 文本排版的结构化签名。"""
    if inspect.isclass(callable_object) and issubclass(callable_object, Enum):
        return "enum(value)"

    signature = inspect.signature(callable_object)
    parameters = tuple(
        (
            parameter.name,
            parameter.kind.name,
            _canonical_annotation(parameter.annotation),
            _canonical_default(parameter.default),
        )
        for parameter in signature.parameters.values()
    )
    return repr((parameters, _canonical_annotation(signature.return_annotation)))


def _signature_digest(callable_object: object) -> str:
    """返回规范化签名的短摘要。"""
    signature = _canonical_signature(callable_object)
    return hashlib.sha256(signature.encode()).hexdigest()[:16]


@pytest.mark.parametrize(("module_name", "expected"), EXPECTED_EXPORTS.items())
def test_public_exports_resolve(module_name: str, expected: tuple[str, ...]) -> None:
    module = importlib.import_module(module_name)

    assert sorted(module.__all__) == sorted(expected)
    assert len(module.__all__) == len(expected)
    for name in expected:
        assert getattr(module, name) is not None


def test_public_callable_signatures_match() -> None:
    for symbol, expected_digest in EXPECTED_SIGNATURE_DIGESTS.items():
        module_name, name = symbol.rsplit(".", maxsplit=1)
        public_object = getattr(importlib.import_module(module_name), name)
        signature = _canonical_signature(public_object)
        actual_digest = _signature_digest(public_object)

        assert actual_digest == expected_digest, f"{symbol} signature drifted: {signature}"


def test_enum_constructor_signature_is_normalized() -> None:
    assert _canonical_signature(Enum) == "enum(value)"


@pytest.mark.parametrize(("symbol", "expected"), EXPECTED_ENUM_VALUES.items())
def test_public_enum_values_match(symbol: str, expected: tuple[tuple[str, str], ...]) -> None:
    module_name, name = symbol.rsplit(".", maxsplit=1)
    enum_class = getattr(importlib.import_module(module_name), name)

    assert tuple((member.name, member.value) for member in enum_class) == expected


@pytest.mark.parametrize(("symbol", "expected_digest"), EXPECTED_METHOD_SIGNATURE_DIGESTS.items())
def test_public_method_signatures_match(symbol: str, expected_digest: str) -> None:
    module_name, class_name, method_name = symbol.rsplit(".", maxsplit=2)
    public_class = getattr(importlib.import_module(module_name), class_name)
    public_method = getattr(public_class, method_name)
    signature = _canonical_signature(public_method)

    assert _signature_digest(public_method) == expected_digest, f"{symbol} signature drifted: {signature}"


def test_public_method_snapshot_is_complete() -> None:
    discovered: set[str] = set()
    for module_name, exports in EXPECTED_EXPORTS.items():
        module = importlib.import_module(module_name)
        for class_name in exports:
            public_object = getattr(module, class_name)
            if not inspect.isclass(public_object):
                continue
            for method_name in public_object.__dict__:
                if method_name.startswith("_") or not callable(getattr(public_object, method_name, None)):
                    continue
                discovered.add(f"{module_name}.{class_name}.{method_name}")

    assert discovered == set(EXPECTED_METHOD_SIGNATURE_DIGESTS)


@pytest.mark.parametrize(("public_name", "target"), EXPECTED_CLEANING_TARGETS.items())
def test_cleaning_lazy_exports_resolve_to_original_object(public_name: str, target: str) -> None:
    cleaning = importlib.import_module("image_gallery.cleaning")
    module_name, target_name = target.rsplit(".", maxsplit=1)
    original_object = getattr(importlib.import_module(module_name), target_name)

    assert getattr(cleaning, public_name) is original_object


def test_cleaning_unknown_export_raises_attribute_error() -> None:
    cleaning = importlib.import_module("image_gallery.cleaning")

    with pytest.raises(AttributeError, match="not_a_public_export"):
        assert cleaning.not_a_public_export is not None
