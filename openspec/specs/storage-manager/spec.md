# storage-manager Specification

## Purpose

定义独立 StorageManager 对 file 与 S3-compatible Prefix、凭证引用、路径安全、SHA-256 内容身份、托管对象提升和图片物理位置的稳定契约。
## Requirements
### Requirement: StorageManager 是独立包
系统 SHALL 在 `image_gallery.storage_manager` 提供不依赖 DatasetManager 的 StorageManager，并且 StorageManager 不理解 Repo、Dataset、Branch、Checkpoint、Tag 或 Vector。

#### Scenario: 独立使用 StorageManager
- **WHEN** 非 Dataset 功能创建 StorageManager 并注册 Prefix
- **THEN** 可以执行 bytes IO 而无需创建 DatasetManager 或 DatasetRepo

### Requirement: Storage Prefix 和凭证分离
StorageManager SHALL 以稳定 `storage_prefix_id` 注册 file 与 S3-compatible Prefix，并仅保存可由 CredentialProvider 解析的 secret reference，不在 DTO、日志或 Dataset 行中保存 secret。

#### Scenario: 解析 Prefix
- **WHEN** 使用有效 Prefix ID 和相对路径读取对象
- **THEN** StorageManager 使用绑定的 Backend、root 和 credential reference 创建或复用客户端

### Requirement: 相对路径安全
StorageManager SHALL 拒绝绝对路径、`..`、root escape、不规范分隔符和不安全符号链接，并将合法路径规范化为 POSIX 相对路径。

#### Scenario: 拒绝路径逃逸
- **WHEN** relative_path 逃逸 Prefix root
- **THEN** 在任何对象 IO 前返回稳定路径安全错误

### Requirement: SHA-256 内容身份
StorageManager SHALL 根据实际图片 bytes 生成规范 `sha256:<64 lowercase hex>` 身份，并拒绝与调用方预期 hash 不一致的内容。

#### Scenario: 托管 bytes 计算身份
- **WHEN** 写入托管图片 bytes
- **THEN** StorageManager 返回根据实际 bytes 计算的 asset_id 和确定性托管路径

#### Scenario: 外部引用验证
- **WHEN** 新外部 locator 进入 Dataset
- **THEN** StorageManager 实际读取 bytes、计算 SHA-256，并在不匹配时拒绝操作

### Requirement: 托管对象内容寻址且不可覆盖
StorageManager SHALL 先把 managed bytes 写入 operation 临时命名空间，再提升到由 SHA-256 推导的不可变正式路径；重复内容写入 SHALL 幂等复用。

#### Scenario: 重复托管内容
- **WHEN** 两次写入相同 bytes
- **THEN** 两次返回相同 asset_id 和正式位置，第二次不得覆盖不同内容

### Requirement: 一组字段构成图片位置
StorageManager SHALL 使用 `storage_prefix_id + relative_path` 定位对象，不要求额外 locator 字段或全局 hash-to-location registry。

#### Scenario: DatasetView 委托读取
- **WHEN** DatasetView 使用行内 Prefix ID 与相对路径读取图片
- **THEN** StorageManager 返回该位置的 bytes，且 source_uri 不参与路由

### Requirement: 显式完整性验证
普通读取 SHALL NOT 自动重算整张图片 hash；显式 verify 操作 SHALL 重新读取 bytes 并与 asset_id 比较。

#### Scenario: 外部对象被替换
- **WHEN** 显式验证发现 locator 当前 bytes 与行内 asset_id 不一致
- **THEN** 返回完整性错误且不得静默改写 Dataset 行

### Requirement: StorageManager 内部重构兼容性
系统 SHALL 在内部路径与 Backend 职责拆分后保持 StorageManager 的公开导出、方法签名、Prefix 注册、相对路径安全、bytes IO、内容寻址、managed recovery、完整性验证和 Backend client 生命周期语义不变。

#### Scenario: Prefix 注册与恢复保持
- **WHEN** 调用方注册 file 或 S3-compatible Prefix，或用稳定 Prefix ID 恢复冻结定义
- **THEN** 系统保持原有名称和 ID 唯一性、root 规范化、凭证引用隔离与冲突异常

#### Scenario: 路径在 Backend IO 前验证
- **WHEN** 调用方传入绝对路径、root escape、不安全符号链接或非法保留路径
- **THEN** 系统在 file 或 S3 Backend IO 前返回相同的稳定路径安全错误

#### Scenario: 普通对象 IO 保持
- **WHEN** 调用方通过 file 或 S3-compatible Prefix 读写普通对象
- **THEN** 系统保持 overwrite、对象不存在、路径规范化和 client 复用语义

#### Scenario: 托管对象提升与恢复保持
- **WHEN** 托管写入在 staging 写入后中断并随后执行恢复
- **THEN** 系统根据真实 bytes 幂等提升到相同 SHA-256 路径、清理成功恢复的临时命名并保持完整性检查

#### Scenario: Backend client 关闭保持
- **WHEN** StorageManager 被关闭或退出上下文
- **THEN** 系统按 fsspec Backend 能力释放缓存 client、避免重复关闭由 finalizer 管理的 s3fs session，并清空缓存

#### Scenario: 两套存储平台保持隔离
- **WHEN** 调用方独立使用 `image_gallery.storage_manager`
- **THEN** 系统不依赖旧 `image_gallery.storage`，也不获得 Repo、Dataset、Branch、Checkpoint、Tag 或 Vector 领域能力
