## MODIFIED Requirements

### Requirement: VectorField 属于 DatasetRepo
DatasetRepo SHALL 通过 `repo.schema` facade 管理 Repo 内命名唯一的 VectorField；每个字段 SHALL 锁定已注册 `model_id`、模型配置指纹、维度、数值类型和距离度量，且名称不得与 Repo 内任一 Dataset 普通列冲突。

#### Scenario: 创建模型绑定字段
- **WHEN** 调用方执行 `repo.schema.add_vector(name, model_id, distance)` 且模型已注册
- **THEN** 字段定义和冻结模型信息在一个 PostgreSQL transaction 中可见或均不可见

#### Scenario: 拒绝未知模型
- **WHEN** 创建 VectorField 时 model_id 未在 DatasetManager 的 ModelManager 注册
- **THEN** 创建失败且不产生部分字段元数据

### Requirement: Vector 空间和验证集不可修改
VectorField 创建后 MUST 拒绝修改名称、`model_id`、模型配置指纹、维度、数值类型或距离度量；同名且定义完全一致的创建请求 SHALL 幂等返回原字段。

#### Scenario: 尝试更换绑定模型
- **WHEN** 调用方以同一字段名请求不同 model_id、模型指纹或空间参数
- **THEN** 操作失败且原定义保持不变

### Requirement: 独立写入需要来源 View 成员证明
`Dataset.generate_embed` SHALL 在未传 `source` 时固定指定 Branch 的当前 Head（默认 `main`），在传入 `source` 时要求其属于当前 Dataset，并 SHALL 只为最终固定 View 的 asset_id 生成向量；系统不得扫描其他 Dataset 或推断全 Repo 资产集合。

#### Scenario: 默认生成 main Head
- **WHEN** 调用方只提供 field
- **THEN** 系统在调用开始时固定当前 Dataset 的 main Head，并为该 Snapshot 的全部成员生成

#### Scenario: 生成指定 Branch Head
- **WHEN** 调用方未传 source 但指定 branch
- **THEN** 系统在调用开始时固定该 Branch 当前 Head，后续 Branch 推进不改变本次成员范围

#### Scenario: 生成指定 View
- **WHEN** source 是当前 Dataset 的精确 View
- **THEN** 系统只读取该 View 固定 Snapshot 的成员和图片位置

#### Scenario: 拒绝其他 Dataset 的 View
- **WHEN** source View 属于其他 Dataset，即使二者属于同一 Repo
- **THEN** 请求在图片读取和模型推理前失败且不写入向量

#### Scenario: 拒绝歧义来源
- **WHEN** 调用方同时传入 source 和非默认 branch
- **THEN** API 拒绝请求且不读取图片或运行模型

### Requirement: 默认跳过且显式覆盖
`generate_embed` SHALL 在 `overwrite=False` 时跳过已有 Repo 当前值并只生成缺失值，在 `overwrite=True` 时为 View 全部成员重新生成并替换已有值；成功结果 SHALL 原子返回 generated、updated、skipped 计数。

#### Scenario: 默认重复生成
- **WHEN** View 同时包含已有和缺失向量且 overwrite 为 false
- **THEN** 已有值不进入模型推理、缺失值被生成，整个结果在一个 transaction 中发布

#### Scenario: 推理中途失败
- **WHEN** 任一图片读取、完整性校验、模型推理或输出基础校验失败
- **THEN** 本次请求不发布任何新值或覆盖值且已有向量保持不变

### Requirement: Vector-only 不推进 Dataset 历史
`generate_embed` SHALL 只改变 Repo 当前向量，不创建或移动任何 Iceberg Branch、Snapshot 或 Checkpoint。

#### Scenario: Checkpoint 后覆盖向量
- **WHEN** 创建 Checkpoint 后对该 View 执行 overwrite 生成
- **THEN** Checkpoint 数据保持不变，但通过该 View 查询 VectorField 时返回新的 Repo 当前值

### Requirement: 向量在 Repo 内按内容共享
系统 SHALL 以 `(repo_id, vector_field_id, asset_id)` 唯一保存 pgvector 当前值，使同 Repo 多个 Dataset 中相同 asset_id 读取同一向量。

#### Scenario: 跨 Dataset 复用
- **WHEN** 两个 DatasetView 包含相同 asset_id
- **THEN** 通过同一 VectorField 查询时返回同一个 Repo 当前值

## ADDED Requirements

### Requirement: 生成前验证冻结模型绑定
`generate_embed` SHALL 解析 VectorField 绑定的模型，并 MUST 在推理前确认当前注册定义的配置指纹、维度和 dtype 与字段冻结值完全一致。

#### Scenario: 重启后注册配置漂移
- **WHEN** 当前 ModelManager 中同一 model_id 的定义与 VectorField 冻结指纹不一致
- **THEN** 生成失败且不读取图片、不运行模型、不写入向量

### Requirement: 生成使用 View 冻结位置和可信图片
`generate_embed` SHALL 使用 source View 每行的 `storage_prefix_id + relative_path` 通过 StorageManager 读取图片，并 MUST 在推理前验证 bytes 与 asset_id 的 SHA-256 内容身份一致。

#### Scenario: 图片内容被替换
- **WHEN** View 指向的位置可读取但 bytes 的 SHA-256 不等于 asset_id
- **THEN** 整次生成失败且不发布任何向量

### Requirement: Dataset Commit 不接受向量
系统 MUST 拒绝通过 Dataset Commit、VectorField.write 或其他公开通用写入入口提交调用方生成的向量；`Dataset.generate_embed` SHALL 是公开生成和发布 Repo 向量的唯一入口。

#### Scenario: 调用方尝试直接写向量
- **WHEN** 调用方在 Commit frame、fields 或旧 VectorField 写入入口提供 embedding
- **THEN** 请求失败且提示使用绑定模型的 `generate_embed`

## REMOVED Requirements

### Requirement: 写入前验证完整验证集
**Reason**: 冻结验证集和调用方 validation outputs 不能证明目标向量由绑定模型生成，且显著增加调用协议复杂度。

**Migration**: 注册冻结模型，使用 `repo.schema.add_vector(..., model_id=...)` 绑定字段，再调用 `dataset.generate_embed(field=...)` 或显式传入 source View。

### Requirement: Dataset 与 Vector 组合提交原子可见
**Reason**: Dataset Commit 不再接受向量；数据 Snapshot 与 Repo 当前向量分别通过 Commit 和 generate_embed 发布。

**Migration**: 先提交普通 Dataset DataFrame，再从提交后打开的精确 View 调用 generate_embed。

### Requirement: DatasetManager 不负责向量生成
**Reason**: DatasetManager 现在显式组合 ModelManager 和 StorageManager，以保证模型、成员、图片与发布边界不可绕过。

**Migration**: 将外部 embedding 调用替换为 DatasetManager 下的 `dataset.generate_embed`。

### Requirement: Vector 验证边界具有直接测试证据
**Reason**: validation set 门禁已删除，测试边界改为模型绑定指纹和输出数量、维度、dtype、有限值校验。

**Migration**: 删除 validation outputs 测试并覆盖 ModelManager 基础契约与 generate_embed 原子失败场景。

### Requirement: 组合提交并发冲突具有直接测试证据
**Reason**: Data+Vector 组合提交被删除，不再存在该并发协议。

**Migration**: 分别测试 Dataset Commit 的 Branch 基线冲突和 generate_embed 的单事务发布。
