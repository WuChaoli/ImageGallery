## ADDED Requirements

### Requirement: 新平台 API 独立设计
系统 SHALL 在 `image_gallery.dataset_manager` 中提供新 DatasetManager API，且不得要求兼容现有 `image_gallery.dataset` 或 `image_gallery.storage` 的公开签名和架构。

#### Scenario: 新旧包并存
- **WHEN** 安装包含新平台的版本
- **THEN** 新 API 从 `image_gallery.dataset_manager` 导入，旧包保持可独立导入且不会被新类型隐式替换

### Requirement: DatasetManager 只管理 Backend 和 Repo
DatasetManager SHALL 负责连接生命周期以及 DatasetRepo 的创建、打开和列出，不提供单 Dataset 的 Branch、Checkpoint、commit 或 scan 方法。

#### Scenario: 创建和打开 Repo
- **WHEN** 调用 DatasetManager 创建或打开命名 Repo
- **THEN** 返回 DatasetRepo handle，且 Dataset 局部操作由该 Repo 打开的 Dataset 承担

### Requirement: Repo 是硬隔离边界
系统 SHALL 以不可变 `repo_id` 隔离 Dataset、Tag Definition、VectorField 和向量，并禁止跨 Repo 引用这些对象。

#### Scenario: 相同名称跨 Repo 使用
- **WHEN** 两个 Repo 分别创建同名 Dataset、Tag 或 VectorField
- **THEN** 系统允许创建且两组对象互不影响

#### Scenario: 拒绝跨 Repo 引用
- **WHEN** Dataset 写入另一个 Repo 的 tag_id、vector_field_id 或 DatasetView
- **THEN** 整个操作在产生外部副作用前被拒绝

### Requirement: Repo 对应 Iceberg Namespace
一套 DatasetManager Backend SHALL 承载多个 Repo，且每个 Repo 对应同一 Catalog 中的独立 Iceberg Namespace。

#### Scenario: 创建 Repo Namespace
- **WHEN** 创建新 DatasetRepo
- **THEN** 系统创建或绑定唯一 Namespace，并在 finalize 前不向普通 list/open API 暴露 Repo

### Requirement: Repo 管理多个 Dataset
DatasetRepo SHALL 提供 Dataset 的创建、打开、列出和同 Repo 状态 Clone，并保证 Dataset 名在 Repo 内大小写不敏感唯一。

#### Scenario: 重名 Dataset
- **WHEN** 在同一 Repo 创建仅大小写不同的 Dataset 名称
- **THEN** 第二次创建失败且不得遗留可见 Iceberg Table

### Requirement: Repo 级 Storage Prefix 授权
DatasetRepo SHALL 保存可使用的 Storage Prefix ID；一个 Repo可绑定多个 Prefix，一个 Prefix可绑定多个 Repo，Dataset 只能引用所属 Repo 已授权 Prefix。

#### Scenario: 未授权 Prefix
- **WHEN** Dataset commit 包含未绑定到所属 Repo 的 storage_prefix_id
- **THEN** Commit 在读取或写入图片前失败

### Requirement: MVP 生命周期只增不减
系统 SHALL NOT 在 MVP 公开 DatasetRepo、Dataset、Branch、Checkpoint、VectorField、向量、Storage Prefix 或托管对象的删除能力。

#### Scenario: 检查公开生命周期 API
- **WHEN** 调用方检查新平台公开 API
- **THEN** 不存在上述对象的 delete、purge 或 garbage-collect 入口
