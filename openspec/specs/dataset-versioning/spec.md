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
