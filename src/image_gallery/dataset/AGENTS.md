# `dataset/` 模块指南

## 职责

- 管理表格数据集的加载、写出、扫描、指纹、图片读取和导出协议。
- 通过关联的 Storage 读取 `s3://` 图片，通过 URI 规则读取本地图片。
- 不负责图片对象的物理存储或清洗决策。

## 当前能力与公共入口

从 `image_gallery.dataset` 使用 `Dataset`、`DatasetImage`、读取结果类型、`DatasetLoader`、`DatasetExporter`、`DatasetExportResult` 和 `TabularDatasetExporter`。

## 核心契约与边界

- `image_uri` 是导入后的图片主引用；`source_uri` 只用于来源追溯。
- Dataset 数据落在 Parquet、CSV 或 JSONL；图片 bytes 不由表格层直接拥有。
- 新增数据集格式优先实现 Loader/Exporter 协议，不扩大 `Dataset` 的格式分支。
- 修改公共 API 前检查 `__init__.py` 导出、tests、examples 和 notebooks。

## 开发与验证

- 单元测试：`tests/unit/dataset/`
- 当前行为：`openspec/specs/dataset-management/spec.md`、`openspec/specs/dataset-versioning/spec.md`
- LabelImg 互操作由 `annotations/` 提供。
