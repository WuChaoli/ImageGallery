# Proposal: add-future-capability-placeholders

## Summary

为 PRD 和架构文档中规划但尚未实现的未来能力添加占位 spec，包括图片增强模块、数据集版本管理、内容安全算子和向量索引能力。每个占位 spec 记录能力定位、职责边界、与现有模块关系和扩展约束。

## Added Capabilities

- 新增 image-enhancement spec（图片增强模块占位——V1 不实现，后续在清洗流程之上扩展）
- 新增 dataset-versioning spec（数据集版本管理占位——分支、合并、diff 能力）
- 新增 content-safety-operators spec（内容安全算子占位——NSFW/watermark/text_image 检测）
- 新增 vector-search spec（向量索引能力占位——Milvus/Weaviate 集成）

## Modified Capabilities

无。全部为新增占位 spec。

## Affected Specs

- `specs/image-enhancement/spec.md`（新建）
- `specs/dataset-versioning/spec.md`（新建）
- `specs/content-safety-operators/spec.md`（新建）
- `specs/vector-search/spec.md`（新建）

## Non-Goals

- 不实现任何代码
- 不为太远期的能力建占位（Web 前端、多用户权限、分布式调度）
- 不修改现有 13 个 spec
