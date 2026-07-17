## MODIFIED Requirements

### Requirement: 固定系统字段与开放物理 Schema
每张 Dataset Table SHALL 包含 required `asset_id`、`storage_prefix_id`、`relative_path`，optional `source_uri` 和 required `tag_ids: list<string>`；Dataset SHALL 通过 `dataset.schema` facade 读取列定义并新增可选业务列，且普通列名不得与所属 Repo 的 VectorField 重名。

#### Scenario: 通过 Schema facade 新增普通列
- **WHEN** 调用方执行 `dataset.schema.add_column(...)` 且名称和类型有效
- **THEN** 新可选业务列加入 Dataset Table 并可由 View 读取

#### Scenario: 选择普通列和向量字段
- **WHEN** DatasetView.scan 的 fields 同时指定存在的物理列和所属 Repo VectorField
- **THEN** 返回精确字段投影且不隐藏系统列或改变字段顺序

#### Scenario: 拒绝破坏性 Schema 演进
- **WHEN** 请求 drop、rename、change-type、修改系统字段或创建与 VectorField 同名的普通列
- **THEN** 操作失败且 Branch Head 不变

### Requirement: Dataset Commit 使用完整行 upsert
Dataset SHALL 接受 pandas DataFrame 并按 `asset_id` 写入普通 Iceberg 字段；显式传入 `fields` 时 SHALL patch 指定字段，未传 `fields` 时 SHALL 使用 frame 中普通物理字段执行完整行 upsert。已有 ID 的完整 upsert SHALL 使用完整规范化行替换，逻辑无变化时不得产生新 Snapshot。

#### Scenario: Patch 已有行
- **WHEN** frame 包含已有 asset_id 且显式 fields 只列出部分普通业务字段
- **THEN** 仅指定字段更新，其他字段保持基线 View 中的值

#### Scenario: 新增和完整更新行
- **WHEN** 未传 fields 的 frame 同时包含新 ID 与已有 ID 的完整普通字段
- **THEN** 新 ID 插入、已有 ID 完整替换，并通过一次候选 Snapshot 发布

#### Scenario: 拒绝直接提交向量
- **WHEN** fields 或 frame 包含所属 Repo 的 VectorField 名称
- **THEN** Commit 在写入前失败并指引调用 `dataset.generate_embed()`，Branch 和 Repo 当前向量均不改变

#### Scenario: No-op Commit
- **WHEN** 规范化后所有普通行、Schema 和 tag_ids 均无变化
- **THEN** Commit 返回 no-op，Branch 和 Snapshot 列表不变

### Requirement: Dataset 提供语义 IO
DatasetView SHALL 提供 `scan`、`count`、`preview`、按 asset_id 读取行与图片 bytes 的入口，并把物理 bytes 读取委托给 StorageManager。`scan` 和 `get_rows` SHALL 返回 pandas DataFrame，`get_row` SHALL 返回 pandas Series；fields 可统一引用物理列和所属 Repo VectorField。

#### Scenario: 默认扫描物理字段
- **WHEN** scan 未传 fields
- **THEN** 返回 View 固定 Snapshot 的全部物理字段且不隐式加载 VectorField

#### Scenario: 组合读取普通列和向量
- **WHEN** fields 同时包含物理列与 VectorField
- **THEN** DataFrame 按请求顺序包含固定 Snapshot 的普通值和 Repo 当前向量，缺失向量为 None

#### Scenario: 批量读取向量
- **WHEN** scan 或 get_rows 读取多个 asset_id 的 VectorField
- **THEN** 系统使用批量查询合并向量而不是逐行查询

#### Scenario: 读取图片
- **WHEN** View 中存在 asset_id 且其 Prefix 已授权可解析
- **THEN** 系统使用该行唯一的 storage_prefix_id + relative_path 返回 bytes
