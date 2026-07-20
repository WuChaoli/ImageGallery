## MODIFIED Requirements

### Requirement: 数据集版本管理（PLANNED）
系统 SHALL 在新 `image_gallery.dataset_manager` 平台中以每 Dataset 单 Iceberg Table 提供 Branch、Checkpoint、回退和状态 Clone；旧文件型 Dataset 的核心读写 API 不在本 change 中修改。

#### Scenario: 模块存在性
- **WHEN** 检查新 DatasetManager 平台
- **THEN** 版本能力由 Dataset 和 DatasetView 提供，而不是旧 Dataset 的元数据扩展

#### Scenario: Commit 与内部 Snapshot
- **WHEN** Dataset Commit 产生逻辑数据变化
- **THEN** 推进目标 Iceberg Branch 并产生内部 Snapshot，且只有显式请求 Checkpoint 时才创建公开历史版本

#### Scenario: Checkpoint-only 历史
- **WHEN** 用户列出、打开、回退或从公开历史创建分支
- **THEN** 只接受显式 Checkpoint；公开 API 不接受任意内部 snapshot_id

#### Scenario: 从固定 View 创建 Branch
- **WHEN** 用户从同 Dataset 的非空固定 Branch View 或 Checkpoint View 创建新 Branch
- **THEN** 系统直接让新 Branch 指向该精确 Snapshot，不创建隐式 Checkpoint且不移动来源 ref

#### Scenario: 分支与回退
- **WHEN** 把 Branch 回退到同 lineage 祖先 Checkpoint
- **THEN** 系统使用 Iceberg ref 完成操作；非祖先状态必须创建新 Branch

#### Scenario: 乐观并发
- **WHEN** 推进 Branch 时调用方基线 DatasetView 已不是当前 Head
- **THEN** 操作返回冲突且不执行自动 merge

#### Scenario: Dataset 状态 Clone
- **WHEN** 从精确 DatasetView Clone Dataset
- **THEN** 新 Table 复制该状态但不继承源 Branch、Checkpoint 或 Snapshot 历史

#### Scenario: MVP 不实现复杂历史操作
- **WHEN** 检查 MVP 范围
- **THEN** merge、diff、rebase、cherry-pick、通用 Dataset stash、删除和跨 Repo clone 不存在

### Requirement: Dataset 历史职责拆分保持协议稳定
系统 SHALL 继续通过私有历史协作者实现 Dataset 版本操作，但本 change 明确演进 `Dataset.commit()`、`CommitResult`、Schema DTO、Branch 来源以及 operation kind/phase/intent；未被本 change 修改的 Tag、VectorField、embed 与 DatasetView IO 边界 SHALL 保持不变。

#### Scenario: 公开历史契约按本 change 演进
- **WHEN** 检查 DatasetManager 公开导出和方法签名
- **THEN** CommitMode、递归 Schema DTO、ColumnSpec 与返回 DTO 按本 change 暴露，commit、branch 与 materialize 使用新的显式参数和结果语义

#### Scenario: Durable protocol 可演进且保持可恢复
- **WHEN** 新操作需要记录 Schema additions、Checkpoint、Branch 或 materialize 阶段
- **THEN** 系统可新增或扩展 operation kind、phase 与 intent，但每个已持久化状态仍可幂等完成或稳定失败

#### Scenario: 非历史职责保持原边界
- **WHEN** 使用 Tag、VectorField、embed 或 DatasetView 图片与扫描 API
- **THEN** 系统保持其所有权和持久化边界，不由历史协作者新增无关公开能力

## ADDED Requirements

### Requirement: Commit 可原子创建可恢复 Checkpoint
Dataset Commit SHALL 接受可选 Checkpoint 名称，并在指定名称时把 Schema additions、Branch 候选 Snapshot 发布与 Checkpoint 创建记录在同一 durable operation；operation 只在请求状态全部完成后 finalize。Dataset 层未指定名称时 SHALL NOT 自动创建 Checkpoint。

#### Scenario: Commit 创建命名 Checkpoint
- **WHEN** Commit 成功推进 Branch 且携带未使用的 Checkpoint 名称
- **THEN** 返回的 Branch View 与 Checkpoint View 指向同一 Snapshot，Checkpoint 可由公开 API 列出和重新打开

#### Scenario: No-op Commit 创建 Checkpoint
- **WHEN** Commit 数据逻辑无变化但携带未使用的 Checkpoint 名称且基线非空
- **THEN** 系统不创建新 Snapshot，但为基线 Snapshot 创建 Checkpoint 并返回 changed=False

#### Scenario: Snapshotless 空 Dataset 创建首个 Checkpoint
- **WHEN** snapshotless 空 Dataset 以 empty replace 请求未使用的 Checkpoint 名称
- **THEN** 系统创建首个可读取空 Snapshot 并让 Branch 与 Checkpoint 指向它，逻辑结果返回 changed=False；未请求 Checkpoint 的 empty-to-empty replace 仍为无 Snapshot no-op

#### Scenario: Checkpoint 阶段中断恢复
- **WHEN** Branch 已发布但 Checkpoint 创建或 operation finalize 前中断
- **THEN** recover_operations 幂等创建同名 Checkpoint 并完成 operation，不产生第二个 Snapshot

#### Scenario: 组合发布中间态不可见
- **WHEN** Schema 或 Branch 已发布但 Checkpoint 创建或 operation finalize 前中断
- **THEN** 普通 Head、Checkpoint open/list 与 Schema discovery 返回 reconciling conflict；data/ref-only operation 允许既有固定 View 读取旧 Snapshot，包含 Schema additions 时阻断其默认 scan 与依赖当前 Table Schema 的 IO；恢复 finalize 后新 Schema、Head 与 Checkpoint 一起可见

#### Scenario: Checkpoint 名冲突预检
- **WHEN** 请求的 Checkpoint 名称与 Dataset 既有 ref 或 pending operation 冲突
- **THEN** Commit 在候选 Snapshot 或 Branch 副作用前失败

### Requirement: 同 Dataset 历史修改串行
系统 SHALL 以同一 Dataset history lock 串行该 Dataset 的 Commit、Checkpoint、Branch、Rollback 及其 recovery，并 SHALL 允许不同 Dataset 的历史操作独立进行。固定 source Snapshot 的 Clone/materialize SHALL NOT 锁来源 Dataset；目标新 Dataset 使用 durable 名称预留。

#### Scenario: 同 Dataset 并发历史操作
- **WHEN** 两个调用方并发修改同一 Dataset 的 refs 或 Branch Head
- **THEN** 系统在同一锁域内重新检查 operation status、名称、pending operation、ref 和基线，只有满足约束的操作发布

#### Scenario: 两个恢复者并发处理同一 operation
- **WHEN** 两个 Manager 或 API operation 与 recover_operations 并发处理同一 Dataset
- **THEN** 只有持有同一 Backend identity history lock 的执行者恢复，后获得锁者重读状态且不重复发布

#### Scenario: 不同 Dataset 历史操作
- **WHEN** 两个调用方修改同 Repo 或不同 Repo 的不同 Dataset
- **THEN** 两个 Dataset 使用不同锁域且不因全局互斥而串行

### Requirement: Branch 创建使用 durable operation
从固定 DatasetView 创建 Branch SHALL 持久化来源 Snapshot、目标 ref 与恢复阶段，并在 ref 创建后中断时可幂等完成。

#### Scenario: 从 stale 但有效的固定 Branch View 创建 Branch
- **WHEN** 来源 Branch 已推进但调用方持有的旧 View Snapshot 仍存在
- **THEN** 新 Branch 指向旧 View 的精确 Snapshot，不要求来源仍是 Head，且不创建隐式 Checkpoint

#### Scenario: Branch ref 创建后中断
- **WHEN** Iceberg Branch ref 已创建但 operation 尚未 finalize 时中断
- **THEN** 普通 ref API 不暴露不确定中间态，recover_operations 识别同一 ref 并 finalize 而不重复创建
