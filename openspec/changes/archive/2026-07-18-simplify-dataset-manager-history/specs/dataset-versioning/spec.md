## ADDED Requirements

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
