# `schemas/` 模块指南

## 职责

- 定义原始数据集 Schema，并提供结构校验。
- 不执行数据导入、存储访问或清洗计算。

## 当前能力与公共入口

从 `image_gallery.schemas` 使用 `RawDatasetSchema` 和 `validate_raw_dataset`。

## 核心契约与边界

- Schema 是 Dataset 与 Importers 之间的数据契约，不应依赖具体 Storage 后端。
- 字段增删或语义变化属于产品行为变更，必须同步 OpenSpec、调用方和测试。
- 校验逻辑应返回明确失败原因，不静默修复输入数据。

## 开发与验证

- 单元测试按调用模块放置，并检查 `tests/unit/dataset/` 与 `tests/unit/importers/`。
- 相关行为：`openspec/specs/dataset-management/spec.md`、`openspec/specs/image-import/spec.md`
