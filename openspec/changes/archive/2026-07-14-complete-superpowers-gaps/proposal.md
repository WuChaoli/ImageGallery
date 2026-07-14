## Why

`openspec/specs/` 在从 docs/ 迁移时遗漏了 6 项 superpowers/ 中已明确的设计内容。其中 4 项是已实现功能的规格缺失（语义去重算子、Raw 元数据扩展、导入路径分片、Notebook 基础设施），2 项是未实现功能的行为契约缺失（Dataset I/O 可插拔模型、逐算子预览）。补全这些差距可确保 openspec 成为唯一的行为规范来源。

## What Changes

- 新建 `semantic-duplicate-operator` spec：定义 `duplicate.semantic_duplicate_check` 算子的完整行为契约，包括 SemanticEmbeddingProvider 协议、ONNX DINOv2 默认 provider、Faiss 索引 artifact、可选依赖组
- 新建 `notebook-infrastructure` spec：定义 `notebooks/_helpers/` 包结构、职责分离、确定性采样、验证策略
- 增补 `dataset-management` spec：新增 Dataset.load()/export() 统一 I/O API 和 DatasetLoader/DatasetExporter 可插拔协议（PLANNED）
- 增补 `image-import` spec：新增 Raw 元数据扩展字段完整清单（33 列）、GPS 敏感字段标记、导入路径分片默认参数
- 增补 `cleaning-preview` spec：新增逐算子 drop/review HTML 预览契约（PLANNED）

## Capabilities

### New Capabilities
- `semantic-duplicate-operator`: 语义去重算子的完整行为契约（Provider 协议、Faiss 索引、artifact 存储、可选依赖）
- `notebook-infrastructure`: Notebook 验证基础设施（helpers 包、确定性采样、职责分离、CI 策略）

### Modified Capabilities
- `dataset-management`: 新增 Dataset.load()/export() 统一 I/O 和可插拔协议
- `image-import`: 新增 Raw 元数据扩展字段清单和导入路径分片参数
- `cleaning-preview`: 新增逐算子 drop/review 预览

## Impact

- 新增 2 个 spec 目录：`openspec/specs/semantic-duplicate-operator/`、`openspec/specs/notebook-infrastructure/`
- 修改 3 个现有 spec：`dataset-management`、`image-import`、`cleaning-preview`
- 总 spec 数从 17 增长到 19
- 不涉及代码变更，仅规范补全
