# vector-search Specification

## Purpose
TBD - created by archiving change add-future-capability-placeholders. Update Purpose after archive.
## Requirements
### Requirement: 向量索引能力（PLANNED）
系统 SHALL 在未来提供向量索引能力，支持基于 embedding 的语义搜索和相似图片分析。

#### Scenario: 模块存在性
- **WHEN** 检查向量索引功能
- **THEN** 功能不存在（尚未实现，当前为占位 spec）

#### Scenario: 候选后端
- **WHEN** 未来实现向量索引
- **THEN** 候选后端为 Milvus 或 Weaviate，通过统一 VectorStore 抽象接入

#### Scenario: 与 semantic_duplicate 的关系
- **WHEN** 向量索引能力实现后
- **THEN** semantic_duplicate 算子的 Faiss index 可迁移到 VectorStore 后端，但 Faiss 仍作为轻量本地后端保留

#### Scenario: 使用场景
- **WHEN** 向量索引可用
- **THEN** 支持：语义搜索（以图搜图）、相似图片聚类分析、数据集探索

#### Scenario: 与 Dataset 层的关系
- **WHEN** 向量索引与 Dataset 交互
- **THEN** embedding 向量作为 Dataset 的可选扩展列，不改变核心 schema

#### Scenario: V1 不实现
- **WHEN** 检查 V1 范围
- **THEN** 向量索引不在 V1 实现范围内

