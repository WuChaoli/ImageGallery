# dataset-manager-demo Specification

## Purpose
定义使用固定本地图片和真实 Backend 演示 DatasetManager 完整生命周期的可执行中文 Notebook 契约。
## Requirements
### Requirement: 演示材料固定且可追溯
系统 SHALL 在 `examples/dataset_manager_demo/materials/` 提供从现有 MinIO `sample_1000` 以固定随机种子无放回抽取的 20 张本地原始图片和 manifest。

#### Scenario: 校验提交的演示材料
- **WHEN** 读取 manifest 并检查演示材料目录
- **THEN** 恰好存在 20 个唯一且可解码的图片文件，每项 SHA-256 与 manifest 一致，并保留原始 image_uri、抽样 seed 和本地相对路径

#### Scenario: 从离线材料运行演示
- **WHEN** 源 `sample_1000` MinIO 不可连接但目标 demo Backend 已可用
- **THEN** Notebook 仍能仅使用已提交的 20 张本地图片执行 Dataset 导入

### Requirement: Notebook 自动探测已有环境
Notebook SHALL 自动读取候选 `.env`，对 PostgreSQL/pgvector、PyIceberg Catalog/Warehouse 和 MinIO 执行有界检查，并仅在全部检查通过后默认选择已有环境。

#### Scenario: 已有环境可连接
- **WHEN** `.env` 配置完整且全部 Backend 检查成功
- **THEN** Notebook 清楚显示选中的外部端点并使用 existing session 继续，且不创建容器

#### Scenario: 配置缺失或连接失败
- **WHEN** `.env` 不存在、字段不完整或任一服务不可连接
- **THEN** Notebook 以中文列出具体问题、`.env.example` 修改指导和显式创建 demo Backend 的命令，并阻止业务旅程继续

### Requirement: 用户可显式创建或重建隔离演示环境
系统 SHALL 提供由用户主动调用的命令，用真实 PostgreSQL/pgvector、PyIceberg SqlCatalog/Warehouse 和 MinIO 创建、重建和清理带固定 demo 标识的隔离 Backend。

#### Scenario: 创建新的 demo Backend
- **WHEN** 用户显式执行创建命令且 Docker 可用
- **THEN** 系统启动隔离服务、生成不覆盖 `.env` 的 `.env.demo`、验证连接并返回 managed session

#### Scenario: 显式重建 demo Backend
- **WHEN** 用户以 recreate 选项执行命令
- **THEN** 系统只删除并重建由 demo helper 创建且 label 匹配的容器与 volume，不影响其他 Docker 或外部资源

#### Scenario: 清理已有外部环境
- **WHEN** 当前使用 existing session
- **THEN** 容器停止或 volume 删除 API 拒绝该 session，演示清理最多删除本次创建的 Repo namespace 和对象前缀

### Requirement: 单 Notebook 演示完整 Dataset 生命周期
系统 SHALL 在一个中文 Notebook 中使用选定的真实 Backend 连续演示 DatasetManager 的主要用户旅程。

#### Scenario: 从导入到版本分叉
- **WHEN** 用户从头执行 Notebook 的业务章节
- **THEN** 系统创建 Repo、Dataset、Tag，托管导入 20 张图片并提交 V1，读取行和图片，再创建 Checkpoint 与 experiment Branch 并分别推进 main 和 experiment

#### Scenario: 模型托管的向量生成
- **WHEN** 用户执行向量生命周期章节
- **THEN** Notebook 展示冻结 Model 定义和强绑定 VectorField，默认对 main Head 生成向量，以 DataFrame 同时读取普通列与向量列，并演示重复调用跳过、覆盖生成和指定 View 范围
- **AND** Notebook 验证向量生成不会创建或移动 Iceberg Snapshot，并解释 Repo 当前向量按 asset_id 复用的语义

#### Scenario: 回退与 Clone
- **WHEN** 用户继续执行高级生命周期章节
- **THEN** 系统演示固定 View、Branch 回退和从固定 View Clone

#### Scenario: 关闭并重新连接
- **WHEN** Notebook 关闭第一组 Manager 和 Storage 客户端后以同一配置重建客户端
- **THEN** Repo、Dataset、Refs、Clone、图片、Tag、冻结模型定义、VectorField 和已生成向量均可重新打开并保持持久状态

### Requirement: 演示导入适配不改变生产 API
在正式 Importer 接入 DatasetManager 之前，系统 SHALL 将临时演示 adapter 限制在 examples 范围，并保持 Notebook 主生命周期与具体 importer 实现解耦。

#### Scenario: 检查包边界
- **WHEN** 构建并检查生产 wheel 与 `image_gallery` 公共导出
- **THEN** 演示 adapter 不进入 wheel、不从生产包导出且正式 Importer API 没有变化

### Requirement: Notebook 可重复且可自动验证
Notebook MUST 不依赖隐藏的 kernel 状态，并 SHALL 提供自动化验证覆盖材料、环境选择、安全边界和真实 Backend 从头执行。

#### Scenario: 从干净 kernel 执行 managed 路径
- **WHEN** 自动化测试在隔离目录以 managed demo Backend 从第一单元执行到最后一单元
- **THEN** 所有单元成功，模型注册、向量生成、跳过、覆盖、指定 View、Snapshot 不变和重连恢复断言通过，输出不包含凭证且测试结束无遗留 demo 容器或客户端进程

#### Scenario: 检查中文教学内容
- **WHEN** 检查 Notebook 和 README 的用户说明
- **THEN** 环境配置、每个生命周期阶段、模型托管向量语义、错误恢复和清理步骤均有中文解释，代码实体名称保持英文
