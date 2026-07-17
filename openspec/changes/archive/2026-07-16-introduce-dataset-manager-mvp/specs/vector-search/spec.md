## MODIFIED Requirements

### Requirement: 向量索引能力（PLANNED）
系统 SHALL 在新 DatasetManager 平台先提供 DatasetRepo 级 VectorField 和 pgvector 当前值存储，并把 ANN、语义搜索和相似图片分析保留为后续能力。

#### Scenario: MVP 模块能力
- **WHEN** 检查本 change 的向量功能
- **THEN** 系统提供空间锁定、验证集门禁、写入和按 asset_id 读取，但不提供搜索或索引 API

#### Scenario: 存储后端
- **WHEN** 保存 Repo 当前向量
- **THEN** 使用 PostgreSQL pgvector，并按 repo_id、vector_field_id、asset_id 隔离

#### Scenario: 与 semantic_duplicate 的关系
- **WHEN** 本 change 完成
- **THEN** 现有 semantic_duplicate 算子与本地 Faiss 行为不迁移，未来是否接入 Repo VectorField 另行设计

#### Scenario: 未来使用场景
- **WHEN** 后续实现查询能力
- **THEN** 可以在 Repo 当前向量上增加以图搜图、聚类和数据集探索，但不得假定向量随 Dataset Checkpoint 版本化

#### Scenario: 与 Dataset 层的关系
- **WHEN** 相同 asset_id 出现在同 Repo 多个 Dataset
- **THEN** 向量是 Repo 级当前值而不是 Dataset Schema 扩展列，Tag 和业务数据仍属于各 Dataset Iceberg 历史

#### Scenario: Generation 不在范围
- **WHEN** 检查 VectorField API
- **THEN** 系统不负责模型、Generation 或 embedding 任务生命周期
