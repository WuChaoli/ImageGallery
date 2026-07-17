# vector-search Specification

## Purpose

定义 DatasetRepo 级当前向量存储能力，以及与未来搜索和现有 semantic_duplicate 的边界。

## Requirements

### Requirement: 向量索引能力（PLANNED）
系统 SHALL 在新 DatasetManager 平台提供 DatasetRepo 级 VectorField 和 pgvector 当前值存储，并把 ANN、语义搜索和相似图片分析保留为后续能力。VectorField SHALL 只描述冻结向量空间，模型定义与推理由 ModelManager 管理，Dataset/View 范围的生成和发布由 `Dataset.generate_embed()` 管理。

#### Scenario: MVP 模块能力
- **WHEN** 检查当前向量功能
- **THEN** 系统提供空间锁定、模型托管生成、按 asset_id 读取和当前值发布，但不提供搜索或 ANN API

#### Scenario: 存储后端
- **WHEN** 保存 Repo 当前向量
- **THEN** 使用 PostgreSQL pgvector，并按 repo_id、vector_field_id、asset_id 隔离

#### Scenario: 与 semantic_duplicate 的关系
- **WHEN** 当前 DatasetManager 能力完成
- **THEN** 现有 semantic_duplicate 算子与本地 Faiss 行为不迁移，未来是否接入 Repo VectorField 另行设计

#### Scenario: 未来使用场景
- **WHEN** 后续实现查询能力
- **THEN** 可以在 Repo 当前向量上增加以图搜图、聚类和数据集探索，但不得假定向量随 Dataset Checkpoint 版本化

#### Scenario: 与 Dataset 层的关系
- **WHEN** 相同 asset_id 出现在同 Repo 多个 Dataset
- **THEN** 向量是 Repo 级当前值而不是 Dataset Schema 扩展列，Tag 和业务数据仍属于各 Dataset Iceberg 历史

#### Scenario: Generation 职责边界
- **WHEN** 检查 VectorField、ModelManager 与 Dataset API
- **THEN** VectorField 不直接执行 Generation，ModelManager 负责模型与推理运行时，Dataset.generate_embed 负责固定成员范围并发布 Repo 当前向量
