# `storage/` 模块指南

## 职责

- 提供图片 bytes 的统一存储抽象及本地文件系统、MinIO 实现。
- 负责对象路径安全、存在性、读写删除和批量操作。
- 不负责 Dataset 表结构、导入编排或清洗运行状态。

## 当前能力与公共入口

从 `image_gallery.storage` 使用 `Storage`、`StorageBatchResult`、`FileSystemStorage` 和 `MinioStorage`。公共导出以本目录 `__init__.py` 为准，不在本文复制完整签名。

## 核心契约与边界

- Storage 保存图片对象；Parquet 保存数据集记录，SQLite 保存运行状态。
- 写入结果必须产生可由 Dataset 消费的绝对 `image_uri`。
- 文件系统实现必须拒绝路径逃逸；正式对象默认不得被静默覆盖。
- Storage 不解释 `source_uri` 的业务语义。

## 开发与验证

- 单元测试：`tests/unit/storage/`
- 当前行为：`openspec/specs/storage-system/spec.md`
- 修改 URI、覆盖或批量失败语义时，同步检查 Dataset 与 Importers 调用方。
