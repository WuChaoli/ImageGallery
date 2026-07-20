## ADDED Requirements

### Requirement: Repo 新 Dataset 物化保持不可见创建
DatasetRepo SHALL 把基于同 Repo 固定 DatasetView 的行 Snapshot、operation 开始时冻结的来源当前 Table Schema、显式附加字段、完整 frame、main Snapshot、可选 Checkpoint 和控制面登记作为一个 durable 创建流程，并在 finalize 前对普通 list/open API 隐藏目标 Dataset。系统 SHALL 在任何 Catalog 副作用前建立 `(repo_id, normalized_target_name)` durable 名称预留。

#### Scenario: 新 Dataset 完整发布
- **WHEN** 同 Repo 固定 View、目标名称、完整 frame 和 Schema 全部有效
- **THEN** 返回独立 Dataset、固定 main View 和可选 Checkpoint View，目标 Dataset 仅在所有请求状态完成后可见

#### Scenario: 空 Dataset 完整发布
- **WHEN** 目标 frame 为空且请求初始 Checkpoint
- **THEN** 系统仍创建可读取的空 Snapshot，main 与 Checkpoint 指向该 Snapshot，并只在 finalize 后暴露目标 Dataset

#### Scenario: 新 Dataset 物化失败
- **WHEN** Schema、行、Storage Prefix、Tag Assignment 或 Checkpoint 名称校验失败
- **THEN** 操作在可见登记前失败且普通 API 不返回半创建 Dataset

#### Scenario: 新 Dataset 物化恢复
- **WHEN** 创建流程在 Table、Schema、Snapshot 或 Checkpoint 任一阶段后中断
- **THEN** durable intent 保留来源 Snapshot、目标 Schema、完整 frame 和 Checkpoint 信息，recover_operations 幂等完成且不重复创建可见 Dataset

#### Scenario: 并发同名物化
- **WHEN** 两个调用方并发物化大小写折叠后同名的 Dataset
- **THEN** 只有取得 durable 名称预留的 operation 可产生 Catalog 副作用，loser 稳定失败且不误删 winner 的 Table 或 registration

#### Scenario: 中断后的同名重试
- **WHEN** 名称预留所属 operation 中断后收到同名重试或 recovery
- **THEN** 只有同一 operation 可接管预留并幂等完成，普通重试不得创建第二张 Table

#### Scenario: 来源固定后 Schema 演进
- **WHEN** 固定来源 View 后来源 Dataset 又新增列，再开始 materialize operation
- **THEN** 新 Dataset 使用 operation 开始时冻结的来源当前 Table Schema，而行仍来自 View 的固定 Snapshot，新增列值按 null 规范化
