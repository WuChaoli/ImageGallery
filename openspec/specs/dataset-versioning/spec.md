# dataset-versioning Specification

## Purpose

定义新 DatasetManager 平台基于 Iceberg ref 的 Branch、Checkpoint、回退与状态 Clone 行为。
## Requirements
### Requirement: 数据集版本管理（PLANNED）
系统 SHALL 在新 `image_gallery.dataset_manager` 平台中以每 Dataset 单 Iceberg Table 提供 Branch、Checkpoint、回退和状态 Clone；旧文件型 Dataset 的核心读写 API 不在本 change 中修改。

#### Scenario: 模块存在性
- **WHEN** 检查新 DatasetManager 平台
- **THEN** 版本能力由 Dataset 和 DatasetView 提供，而不是旧 Dataset 的元数据扩展

#### Scenario: Commit 与内部 Snapshot
- **WHEN** Dataset Commit 产生逻辑数据变化
- **THEN** 推进目标 Iceberg Branch 并产生内部 Snapshot，但不自动创建公开历史版本

#### Scenario: Checkpoint-only 历史
- **WHEN** 用户列出、打开、回退或从历史分支
- **THEN** 只接受显式 Checkpoint；公开 API 不接受任意内部 snapshot_id

#### Scenario: 分支与回退
- **WHEN** 从 Checkpoint 创建 Branch 或把 Branch 回退到同 lineage 祖先 Checkpoint
- **THEN** 系统使用 Iceberg ref 完成操作；非祖先状态必须创建新 Branch

#### Scenario: 乐观并发
- **WHEN** 推进 Branch 时调用方基线 DatasetView 已不是当前 Head
- **THEN** 操作返回冲突且不执行自动 merge

#### Scenario: Dataset 状态 Clone
- **WHEN** 从精确 DatasetView Clone Dataset
- **THEN** 新 Table 复制该状态但不继承源 Branch、Checkpoint 或 Snapshot 历史

#### Scenario: MVP 不实现复杂历史操作
- **WHEN** 检查 MVP 范围
- **THEN** merge、diff、rebase、cherry-pick、stash、删除和跨 Repo clone 不存在

### Requirement: Dataset 历史职责拆分保持协议稳定

系统 SHALL 在把 Dataset 历史、候选 Snapshot 发布和 durable recovery 拆入私有协作模块后，保持 `DatasetManager`、`DatasetRepo`、`Dataset` 与 `DatasetView` 的公开导出和签名不变，并保持当前公开可达的 commit、clone、checkpoint、branch、rollback 以及 commit operation/ref 恢复的持久化、异常、Hook 时序、事务和 Iceberg ref 语义不变。

#### Scenario: 历史操作经私有协作者执行
- **WHEN** 调用方执行 commit、clone、checkpoint、branch 或 rollback
- **THEN** 系统通过私有历史协作者完成操作，返回值、异常类型、Branch Head、Checkpoint 和 Snapshot 行为与拆分前一致

#### Scenario: 中断后恢复保持 durable protocol
- **WHEN** 当前公开 commit 操作在候选写入或 ref 发布阶段中断后重新打开 Backend 并调用 `recover_operations()`
- **THEN** 系统继续使用既有 operation kind、phase、intent、临时 ref 和控制面事务幂等完成或稳定失败

#### Scenario: 非历史职责保持原边界
- **WHEN** 使用 Tag、VectorField、embed 或 DatasetView 图片与扫描 API
- **THEN** 系统保持其实现边界和可观察行为不变，不由历史协作者新增公开能力
