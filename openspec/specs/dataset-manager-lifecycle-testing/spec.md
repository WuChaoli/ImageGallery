# dataset-manager-lifecycle-testing Specification

## Purpose

定义 DatasetManager 测试专用导入边界、真实后端完整生命周期验收，以及测试资源确定性关闭要求。

## Requirements

### Requirement: 测试专用 Importer 不进入生产包
系统 SHALL 在 `tests/` 内提供 DatasetManager 测试专用 Importer，并且该对象不得从 `image_gallery` 生产包导出或被 wheel 包含。

#### Scenario: 检查测试 Importer 边界
- **WHEN** 构建并检查生产 wheel 与 `image_gallery` 公共导出
- **THEN** 测试 Importer 不存在于制品或公共 API 中

### Requirement: 测试 Importer 复用来源解析契约
测试 Importer SHALL 接受现有 `SourceParser` 产生的 `SourceRecord`，读取本地图片 bytes，并通过 StorageManager 托管写入生成规范 asset_id 和位置字段。

#### Scenario: 从真实图片目录导入
- **WHEN** 使用 `LocalPathParser` 解析包含多张图片的隔离目录并执行导入
- **THEN** 每个来源形成一条包含 `asset_id`、`storage_prefix_id`、`relative_path`、`source_uri` 和 `tag_ids` 的 Dataset 行，且图片可按 asset_id 读回

#### Scenario: 不可读取的来源
- **WHEN** SourceRecord 没有可读取的 local_path 或 Storage 写入失败
- **THEN** 测试 Importer 立即失败且不得把部分 Dataset 状态发布为成功 commit

### Requirement: 导入通过精确基线原子提交
测试 Importer MUST 接受目标 Branch 的精确 DatasetView 基线，并把本批全部行作为一次 Dataset commit 发布。

#### Scenario: 成功导入批次
- **WHEN** 全部来源与 Tag 均有效且 Branch Head 等于输入基线
- **THEN** 一次 commit 发布全部行，并返回固定的结果 View、导入数量和 asset IDs

#### Scenario: 导入期间基线过期
- **WHEN** 目标 Branch 在基线 View 打开后已经推进
- **THEN** 导入以稳定冲突失败且不得覆盖当前 Branch Head

### Requirement: 真实后端覆盖完整 Dataset 生命周期
真实后端 E2E SHALL 在 PostgreSQL/pgvector、PyIceberg Warehouse、file 与 MinIO StorageManager 上验证一条连续的 Dataset 用户旅程。

#### Scenario: 导入到多版本分支旅程
- **WHEN** 从真实图片目录导入 V1、创建 Checkpoint 和 experiment Branch，并分别推进 main 与 experiment 到不同状态
- **THEN** Branch Head 显示各自状态，V1 View 与 Checkpoint 保持固定，图片、Tag 和当前 Vector 均按契约读取

#### Scenario: 回退与 Clone
- **WHEN** main 在后续 commit 后回退到其祖先 Checkpoint，并从固定 View 创建 Clone
- **THEN** main 恢复 Checkpoint 数据、experiment 保持分叉状态，Clone 拥有独立历史但复用图片和 Repo 当前向量

#### Scenario: 重启重开
- **WHEN** 关闭 DatasetManager 和 StorageManager 后以相同 Backend 配置和稳定 Prefix ID 创建新客户端
- **THEN** Repo、Dataset、Branch、Checkpoint、Clone、图片、Tag 和 Vector 均可重新打开并保持提交前的持久状态

### Requirement: 真实后端测试资源可确定关闭
真实后端测试 MUST 在成功、断言失败和异常路径关闭 DatasetManager、PyIceberg Catalog、SQLAlchemy engine、StorageManager 客户端和 testcontainers，并提供可识别 setup、body 与 teardown 的诊断阶段。

#### Scenario: E2E 正常完成
- **WHEN** 完整生命周期断言通过
- **THEN** pytest 进程在配置的超时内正常退出且没有遗留测试容器或客户端进程

#### Scenario: E2E 中途失败
- **WHEN** 生命周期任一阶段抛出异常
- **THEN** context manager 仍执行全部资源关闭，并使测试报告指出失败阶段
