## ADDED Requirements

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
