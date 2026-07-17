# repository-tags Specification

## Purpose

定义 Repo 级 Tag Definition 与 Dataset 行内版本化 Assignment 的职责边界。

## Requirements

### Requirement: Tag Definition 属于 DatasetRepo
DatasetRepo SHALL 在 PostgreSQL 管理不可变 tag_id、名称、颜色、描述和 lifecycle，且名称在 Repo 内大小写不敏感唯一。

#### Scenario: Repo 间同名 Tag
- **WHEN** 不同 Repo 创建同名 Tag Definition
- **THEN** 两者均可创建且各自只对所属 Repo 可见

### Requirement: Tag Definition 可重命名和归档
系统 SHALL 允许重命名或归档 Tag Definition，且不得为此改写任何 Dataset Iceberg Table。

#### Scenario: 重命名 Tag
- **WHEN** Tag Definition 改名
- **THEN** 所有 Dataset 仍保存相同 tag_id，并在解析显示信息时看到新名称

#### Scenario: 归档 Tag
- **WHEN** 调用方尝试新增已归档 tag_id
- **THEN** Commit 失败；历史已有 assignment 仍可读取

### Requirement: Tag Assignment 属于 Dataset 行
系统 SHALL 只在 Dataset Iceberg 行的 `tag_ids` 保存 Assignment，不在 PostgreSQL 建立 Assignment 或 membership 副本。

#### Scenario: 相同资产在不同 Dataset 具有不同 Tag
- **WHEN** 两个 Dataset 包含相同 asset_id 并分别提交不同 tag_ids
- **THEN** 两者独立保存且互不覆盖

### Requirement: Tag Assignment 随 Dataset 历史版本化
Tag 变更 SHALL 作为普通 Dataset Commit，使用 Repo Tag Definition 校验、去重和规范排序，并随 Branch 和 Checkpoint 固定。

#### Scenario: Branch 隔离 Tag
- **WHEN** 两个 Branch 为相同 asset_id 提交不同 tag_ids
- **THEN** 各自 View 读取各自 Assignment，Checkpoint 固定创建时的值

#### Scenario: Tag No-op
- **WHEN** 输入 tag_ids 规范化后与当前行相同
- **THEN** 不因 Tag 产生新 Snapshot
