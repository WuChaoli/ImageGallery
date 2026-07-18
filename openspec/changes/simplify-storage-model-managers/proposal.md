## Why

`StorageManager` 同时承担 Prefix 注册、路径安全、Backend client 生命周期、普通 bytes IO、托管对象提升与恢复，`ModelManager` 也同时承担模型定义持久化、Engine 迁移、provider runtime 加载、输出校验与资源关闭。两者作为 DatasetManager 的基础设施边界需要先用 characterization tests 固定契约，再拆分私有职责，降低后续 DatasetManager 重构时的耦合与误改风险。

## What Changes

- 为 StorageManager 的 Prefix、路径、file/S3 bytes IO、managed recovery 和 client 关闭补充 characterization tests。
- 将 StorageManager 的路径规范化、Backend client 构造/缓存/关闭和 Backend 特定读写下沉到私有实现，保留稳定门面。
- 为 ModelManager 的 Engine 绑定、provider runtime 缓存、凭证解析、输出校验和重复关闭补充 characterization tests。
- 将 ModelManager 的冻结定义/持久化模型与 provider runtime 生命周期拆分为私有职责，保留稳定门面。
- 保持所有公开导出、类方法签名、返回值、异常、路径安全、内容完整性、凭证隔离和资源所有权语义不变。
- 不修改 DatasetManager、旧 `storage` 平台，不新增 Backend 或 provider，不引入新依赖。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `storage-manager`: 明确内部职责拆分后 Prefix、路径安全、内容寻址、恢复和 Backend client 生命周期必须保持兼容。
- `model-manager`: 明确内部职责拆分后模型持久化、provider 加载、输出校验和关闭生命周期必须保持兼容。

## Impact

- 影响 `src/image_gallery/storage_manager/`、`src/image_gallery/model_manager/` 的私有实现和对应单元测试。
- DatasetManager 仅做兼容性与生命周期回归验证，不修改其实现。
- 不影响包级 `__all__`、公开签名、数据库 schema、对象路径、依赖或旧平台边界。
