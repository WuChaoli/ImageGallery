# `storage_manager/` 模块指南

## 职责

- 独立管理 file 与 S3-compatible Storage Prefix、secret reference、路径安全和 bytes IO。
- 计算并验证 SHA-256 内容身份，管理不可覆盖的内容寻址对象和可恢复 staging promote。
- 不理解 Repo、Dataset、Branch、Checkpoint、Tag 或 Vector。

## 当前能力

- 支持稳定 Prefix ID、按 Backend 隔离的 fsspec client、托管写入、外部引用验证和显式完整性检查。
- 拒绝绝对路径、root escape、危险符号链接和保留命名空间的外部访问。

## 公共入口

- 从 `image_gallery.storage_manager` 导入 `StorageManager`、`StoragePrefix`、`StoredObject` 和稳定异常。

## 核心契约与边界

- 凭证只通过 `CredentialProvider` 解析 secret reference，不进入 DTO、Dataset 行或日志。
- 图片位置固定为 `storage_prefix_id + relative_path`；`source_uri` 不参与物理路由。
- 普通读取不自动重算 hash；只有显式 verify 执行完整性验证。
- Prefix registry 由部署配置 bootstrap；重启后必须使用相同 `prefix_id` 重新注册非敏感配置，secret 仍只通过 CredentialProvider 解析。
- 使用 context manager 或 `close()` 释放缓存的 fsspec/S3 客户端。

## 开发与验证

- 单元测试：`uv run pytest tests/unit/storage_manager`
- S3-compatible 真实链路：`uv run pytest -m dataset_backend tests/integration/dataset_manager`

## 相关文档

- 当前产品行为：`openspec/specs/storage-manager/spec.md`
- 面向用户的用法：根目录 `README.md`
