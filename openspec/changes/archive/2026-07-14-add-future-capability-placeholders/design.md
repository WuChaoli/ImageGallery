# Design: add-future-capability-placeholders

## Context

PRD 和架构文档中规划了多个尚未实现的能力方向。为防止这些规划在迁移到 openspec 后丢失，创建占位 spec 记录其定位、职责边界和扩展约束。

## Goals

- 为 4 个未来能力创建占位 spec
- 每个占位明确与现有模块的关系和边界
- 约束未来实现时的架构一致性

## Non-Goals

- 不实现任何代码
- 不为太远期的能力建占位（Web 前端、多用户权限、分布式调度）

## Key Decisions

### D1: 占位 spec 内容标准

每个占位 spec 包含：
- 模块存在性和当前状态
- 职责边界（只做什么、不做什么）
- 与现有模块的依赖关系
- 未来扩展约束

### D2: 选择的 4 个能力

| 能力 | 选择理由 |
|------|----------|
| image-enhancement | PRD 明确规划，与 cleaning 模块有清晰边界 |
| dataset-versioning | 架构文档中多次提及，与 Dataset 层有明确接口 |
| content-safety-operators | PRD 列出 NSFW/watermark 算子分类，属于 operators 扩展 |
| vector-search | 架构文档规划 Milvus/Weaviate 集成，属于独立能力域 |

### D3: 排除的能力

| 能力 | 排除理由 |
|------|----------|
| Web 前端 | 太远期，V1 明确不实现 |
| 多用户权限 | 太远期 |
| 分布式调度 | 太远期，且架构设计方向未定 |
