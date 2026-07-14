## Context

`openspec/specs/` 当前有 17 个 spec（62 requirements），但在从 `docs/superpowers/` 迁移时遗漏了 6 项已明确的设计内容。本次 change 仅补全规范，不涉及代码变更。

已实现功能的规格缺失：语义去重算子、Raw 元数据扩展字段、导入路径分片参数、Notebook 验证基础设施。
未实现功能的行为契约缺失：Dataset I/O 可插拔模型、逐算子 drop/review 预览。

## Goals / Non-Goals

**Goals:**
- 将 superpowers/ 中 6 项设计内容沉淀为 openspec spec requirements
- 区分已实现（IMPLEMENTED）和未实现（PLANNED）状态
- 确保 openspec 成为唯一的行为规范来源

**Non-Goals:**
- 不修改任何源代码
- 不重新设计已有功能
- 不覆盖 superpowers/archive/ 中已被后续设计替代的内容

## Decisions

### D1: 语义去重作为独立 spec 而非增补 cleaning-operators
- **选择**：新建 `semantic-duplicate-operator` spec
- **理由**：语义去重有独立的 Provider 协议、可选依赖组、artifact 存储模型，复杂度高于普通算子。独立 spec 便于后续扩展（如接入向量数据库）

### D2: Raw 元数据扩展合并到 image-import spec
- **选择**：增补 `image-import` 而非新建 `raw-metadata` spec
- **理由**：元数据字段由 ImportPipeline 在导入时填充，是 image-import 职责的一部分。RawDatasetSchema 已在 image-import spec 中定义

### D3: 导入路径分片合并到 image-import spec
- **选择**：增补 `image-import` 的日期分片 requirement
- **理由**：路径分片是存储层的实现细节，与"日期分片存储路径"requirement 天然关联

### D4: Dataset I/O 可插拔模型标记为 PLANNED
- **选择**：Dataset.load()/export() API 和 DatasetLoader/DatasetExporter 协议标记为 PLANNED
- **理由**：当前代码仍使用旧的 `from_path`/`export` 签名，破坏式变更尚未实施

### D5: 逐算子预览标记为 PLANNED
- **选择**：per-operator drop/review 预览标记为 PLANNED
- **理由**：当前 preview_html 支持按 action 过滤但不支持逐算子独立导出

### D6: Notebook 基础设施作为独立 spec
- **选择**：新建 `notebook-infrastructure` spec
- **理由**：`notebooks/_helpers/` 有明确的包结构、职责分离和测试策略，虽非 src/ 代码但属于项目工程基线

## Risks / Trade-offs

- **[spec 粒度]** 语义去重独立 spec 增加 spec 数量（17→19），但粒度与现有 pHash 算子在 cleaning-operators 中的覆盖方式一致
- **[archive 依赖]** Raw 元数据扩展和路径分片来自 superpowers/archive/，需确认与当前实现一致 → 通过读取源码验证
- **[PLANNED 标记]** Dataset I/O 和逐算子预览标记为 PLANNED，后续实现时需验证 spec 与实际代码的对齐
