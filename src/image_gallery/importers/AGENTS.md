# `importers/` 模块指南

## 职责

- 解析本地路径、URL 列表和数据集文件，提取元数据并通过 Storage 导入图片。
- 生成符合 RawDatasetSchema 的 Dataset 和逐项导入结果。
- 不负责后续清洗、可视化或数据集导出。

## 当前能力与公共入口

从 `image_gallery.importers` 使用 `ImportPipeline`、`ImportResult`、`SourceParser`、`SourceRecord`、`LocalPathParser`、`UrlPathParser` 和 `DatasetParser`。

## 核心契约与边界

- 成功导入后使用 `image_uri` 作为主引用，保留 `source_uri` 追溯来源。
- 单张图片失败应记录在结果中，不得无条件中断整个批次。
- 单元测试不得访问真实网络或 MinIO；外部 IO 使用 fixture 或 mock。

## 开发与验证

- 单元测试：`tests/unit/importers/`
- 当前行为：`openspec/specs/image-import/spec.md`
- Schema 变化同步检查 `schemas/`，存储语义变化同步检查 `storage/`。
