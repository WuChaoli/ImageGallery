## ADDED Requirements

### Requirement: Dataset 统一 I/O API（PLANNED）
系统 SHALL 提供 `Dataset.load()` 和 `Dataset.export()` 作为统一的数据集输入/输出 API，替代旧的 `from_path` 和 `export` 签名。

#### Scenario: Dataset.load 文件路径
- **WHEN** 调用 `Dataset.load(source="/path/to/data.parquet")`
- **THEN** SHALL 从文件路径加载 Dataset（支持 Parquet/CSV/JSONL 格式）

#### Scenario: Dataset.load 协议实例
- **WHEN** 调用 `Dataset.load(source=loader_instance)`
- **THEN** SHALL 接受 `DatasetLoader` 协议实例作为输入

#### Scenario: Dataset.export 协议实例
- **WHEN** 调用 `Dataset.export(exporter=exporter_instance)`
- **THEN** SHALL 接受 `DatasetExporter` 协议实例，返回 `DatasetExportResult`

#### Scenario: 旧 API 移除
- **WHEN** 检查 Dataset API
- **THEN** `Dataset.from_path()` SHALL 被完全移除

### Requirement: DatasetLoader 可插拔协议（PLANNED）
系统 SHALL 定义 `DatasetLoader` 协议，支持自定义数据集加载后端。

#### Scenario: 协议接口
- **WHEN** 实现自定义 Loader
- **THEN** SHALL 实现 `load() -> Dataset` 方法，使用 `@runtime_checkable` 装饰

#### Scenario: 内置 Loader
- **WHEN** 使用内置 Loader
- **THEN** SHALL 提供 `LabelImgLoader(input_dir, annotation_column, dataset_filename, output_filename, strict)` 用于 LabelImg Pascal VOC 目录加载

### Requirement: DatasetExporter 可插拔协议（PLANNED）
系统 SHALL 定义 `DatasetExporter` 协议，支持自定义数据集导出后端。

#### Scenario: 协议接口
- **WHEN** 实现自定义 Exporter
- **THEN** SHALL 实现 `export(dataset: Dataset) -> DatasetExportResult` 方法，使用 `@runtime_checkable` 装饰

#### Scenario: DatasetExportResult
- **WHEN** 导出完成
- **THEN** SHALL 返回冻结 dataclass `DatasetExportResult`，包含 `output_dir`、`output_path`、`image_count`、`annotation_count`、`failures` 字段

#### Scenario: 内置 Exporter
- **WHEN** 使用内置 Exporter
- **THEN** SHALL 提供 `TabularDatasetExporter(output_path, drop_source_uri)` 和 `LabelImgExporter(output_dir, annotation_column, dataset_filename, overwrite)`

#### Scenario: 格式支持范围
- **WHEN** 第一版 I/O 插件
- **THEN** SHALL 仅支持 Parquet/CSV/JSONL 表格导出和 LabelImg Pascal VOC XML 目录导出/加载；SHALL NOT 支持 YOLO、COCO、Label Studio
