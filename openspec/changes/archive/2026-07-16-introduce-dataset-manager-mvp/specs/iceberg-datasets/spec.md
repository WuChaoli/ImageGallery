## ADDED Requirements

### Requirement: 每个 Dataset 一张 Iceberg Table
DatasetRepo SHALL 在创建 Dataset 时创建且只创建一张 Iceberg Table，并同时建立默认 `main` Branch。

#### Scenario: 原子创建 Dataset
- **WHEN** Table 创建或 PostgreSQL registration finalize 中断
- **THEN** 普通 API 不返回半创建 Dataset，recovery 可根据 durable intent 幂等完成

### Requirement: 固定系统字段与开放物理 Schema
每张 Dataset Table SHALL 包含 required `asset_id`、`storage_prefix_id`、`relative_path`，optional `source_uri` 和 required `tag_ids: list<string>`；用户可读取这些列并新增可选业务列。

#### Scenario: 选择任意列
- **WHEN** DatasetView.scan 指定存在的系统列和业务列
- **THEN** 返回精确列投影且不隐藏系统列

#### Scenario: 拒绝破坏性 Schema 演进
- **WHEN** 请求 drop、rename、change-type 或修改系统字段
- **THEN** 操作失败且 Branch Head 不变

### Requirement: 内容身份是行唯一键
系统 SHALL 要求 `asset_id` 是实际图片 SHA-256，且同一 Dataset Snapshot 内一个 asset_id 最多存在一行。

#### Scenario: 重复 asset_id
- **WHEN** 同一 change set 包含重复 asset_id
- **THEN** 整批 Commit 被拒绝

### Requirement: Dataset Commit 使用完整行 upsert
Dataset SHALL 按 asset_id 接受完整行 append/upsert；已有 ID 使用完整规范化行替换，逻辑无变化时不得产生新 Snapshot。

#### Scenario: 新增和更新行
- **WHEN** change set 同时包含新 ID 与已有 ID
- **THEN** 新 ID 插入、已有 ID 完整替换，并通过一次候选 Snapshot 发布

#### Scenario: No-op Commit
- **WHEN** 规范化后所有行、Schema 和 tag_ids 均无变化且没有待发布向量
- **THEN** Commit 返回 no-op，Branch 和 Snapshot 列表不变

### Requirement: DatasetView 固定精确 Snapshot
打开 Branch Head 或 Checkpoint SHALL 返回只读 DatasetView，后续 ref 推进不得改变既有 View 的扫描和图片读取结果。

#### Scenario: Branch 后续推进
- **WHEN** 打开 View 后目标 Branch 收到新 Commit
- **THEN** 既有 View 仍读取打开时 Snapshot，新打开 View 读取新 Head

### Requirement: Dataset 提供语义 IO
DatasetView SHALL 提供 scan、count、preview、按 asset_id 读取行与图片 bytes 的入口，并把物理 bytes 读取委托给 StorageManager。

#### Scenario: 读取图片
- **WHEN** View 中存在 asset_id 且其 Prefix 已授权可解析
- **THEN** 系统使用该行唯一的 storage_prefix_id + relative_path 返回 bytes

### Requirement: Branch 推进使用显式基线
所有推进 Dataset Branch 的操作 MUST 携带该 Branch 的精确 DatasetView 基线，并在当前 Head 与基线不一致时返回冲突。

#### Scenario: 并发提交冲突
- **WHEN** 两个调用方基于同一 View 提交且第一个已推进 Branch
- **THEN** 第二个提交失败，不自动 merge、覆盖或重试

### Requirement: Clone 只复制固定状态
DatasetRepo SHALL 支持从同 Repo 精确 DatasetView 创建新 Dataset，复制 Physical Schema 和全部行，但不继承源历史。

#### Scenario: 从 View Clone
- **WHEN** Clone 成功
- **THEN** 新 Dataset 只有独立 main 和一次初始 Snapshot，不包含源 Branch、Checkpoint 或 Snapshot 历史

#### Scenario: Clone 复用外部数据
- **WHEN** Clone 复制行
- **THEN** 不复制图片 bytes 或 Repo 向量，只复用行内位置和相同 asset_id

### Requirement: Dataset 行位置随历史固定
每个 Dataset Snapshot 中一行 SHALL 只保存一组 storage_prefix_id + relative_path；修改位置必须通过普通 Commit，并由 Checkpoint 固定。

#### Scenario: 更新图片位置
- **WHEN** 使用相同 asset_id 提交不同但校验匹配的已授权位置
- **THEN** 新 Snapshot 使用新位置，旧 DatasetView 仍使用旧位置
