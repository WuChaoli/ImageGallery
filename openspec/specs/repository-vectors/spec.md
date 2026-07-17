# repository-vectors Specification

## Purpose

定义 DatasetRepo 级 VectorField 的空间契约、完整验证门禁、pgvector 当前值语义，以及 Dataset 数据与调用方向量组合提交时的原子可见边界。

## Requirements

### Requirement: VectorField 属于 DatasetRepo
DatasetRepo SHALL 管理 Repo 内命名唯一的 VectorField；每个字段 SHALL 锁定维度、数值类型、距离度量、比较容差和一套有序验证集。

#### Scenario: 原子创建字段与验证集
- **WHEN** 创建 VectorField
- **THEN** 字段定义、全部验证输入和预期向量在一个 PostgreSQL transaction 中可见或均不可见

### Requirement: Vector 空间和验证集不可修改
VectorField 创建后 MUST 拒绝修改任何空间参数、验证输入、预期输出或比较规则。

#### Scenario: 尝试更换验证集
- **WHEN** 调用方更新已存在 VectorField 的验证集
- **THEN** 操作失败且原定义保持不变

### Requirement: 写入前验证完整验证集
每次写入新向量或覆盖已有向量前，调用方 MUST 提供完整有序验证集输出；系统 SHALL 按锁定规则比较，任一缺失或不匹配均拒绝整批写入。

#### Scenario: 验证输出不匹配
- **WHEN** 任一 probe 的返回向量维度、数值或顺序不满足契约
- **THEN** 不写入任何目标向量

### Requirement: 向量在 Repo 内按内容共享
系统 SHALL 以 `(repo_id, vector_field_id, asset_id)` 唯一保存 pgvector 当前值，使同 Repo 多个 Dataset 中相同 asset_id 读取同一向量。

#### Scenario: 跨 Dataset 复用
- **WHEN** 两个 DatasetView 包含相同 asset_id
- **THEN** 通过同一 VectorField 查询时返回同一个 Repo 当前值

### Requirement: 独立写入需要来源 View 成员证明
VectorField.write MUST 接受所属 Repo 的精确 DatasetView，并要求全部 asset_id 是该 View 的成员；系统不得要求 Repo Asset Registry 或扫描其他 Dataset。

#### Scenario: 非成员 ID
- **WHEN** 写入批次包含不在 source View 中的 asset_id
- **THEN** 整批写入失败

### Requirement: 默认跳过且显式覆盖
Vector 写入 SHALL 在 `overwrite=False` 时插入缺失值并跳过已有值，在 `overwrite=True` 时更新已有值，并原子返回 inserted、updated、skipped 计数。

#### Scenario: 默认重复写入
- **WHEN** 批次包含已存在和缺失向量且 overwrite 为 false
- **THEN** 已有值不变、缺失值插入，整个批次在一个 transaction 中发布

### Requirement: Vector-only 不推进 Dataset 历史
独立向量写入 SHALL 只改变 Repo 当前向量，不创建或移动任何 Iceberg Branch、Snapshot 或 Checkpoint。

#### Scenario: Checkpoint 后覆盖向量
- **WHEN** 创建 Checkpoint 后覆盖某 asset_id 向量
- **THEN** Checkpoint 数据保持不变，但通过该 View 查询 VectorField 时返回新的 Repo 当前值

### Requirement: Dataset 与 Vector 组合提交原子可见
Dataset Commit MAY 附带调用方已生成的向量；系统 MUST 在数据和全部向量均可发布前不向普通 API 暴露任一新状态。

#### Scenario: 向量验证失败
- **WHEN** 组合 Commit 的任一 VectorField 验证失败
- **THEN** Dataset Branch 不推进且没有目标向量被发布

#### Scenario: 候选行证明成员关系
- **WHEN** 组合 Commit 为本次新增行提供向量
- **THEN** 系统允许使用候选行证明 asset_id 成员关系，无需预先存在的 DatasetView 行

### Requirement: DatasetManager 不负责向量生成
系统 SHALL NOT 保存或调用 embedding 模型、Generation 配置或任务，并仅验证与存储调用方提供的向量。

#### Scenario: 检查 VectorField API
- **WHEN** 调用方使用 VectorField
- **THEN** API 提供定义、验证、写入和读取，不提供 generate 或 model lifecycle 方法

### Requirement: Vector 验证边界具有直接测试证据
VectorField 验证集门禁 SHALL 由确定性测试直接覆盖完整性、顺序、维度、有限数值和比较容差，任一失败均不得写入目标向量。

#### Scenario: 验证输出乱序
- **WHEN** 调用方提供数量正确但 probe 顺序不符合冻结验证集的输出
- **THEN** 整批向量写入失败且已有向量保持不变

#### Scenario: 比较容差边界
- **WHEN** 验证输出分别落在冻结容差以内和以外
- **THEN** 容差内输出通过，容差外输出使整批写入失败

#### Scenario: 非有限验证值
- **WHEN** 验证输出或目标向量包含 NaN、正 Inf 或负 Inf
- **THEN** 系统拒绝整批写入且不发布任何新值

### Requirement: 组合提交并发冲突具有直接测试证据
Data+Vector 组合提交 SHALL 由测试证明在目标 Branch 基线过期时既不推进 Dataset，也不发布 pending 或 current vectors。

#### Scenario: 组合提交使用过期基线
- **WHEN** 组合提交携带的 DatasetView 已不再是目标 Branch Head
- **THEN** 操作返回稳定冲突，Dataset 和全部 VectorField 的可见状态均保持不变
