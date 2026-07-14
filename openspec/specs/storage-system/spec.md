# storage-system Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: Storage 抽象接口
系统 SHALL 提供 `Storage` 抽象基类，定义 `write_bytes`、`read_bytes`、`exists`、`delete`、`copy`、`move` 和 `make_image_uri` 方法，作为所有存储后端的统一接口。

#### Scenario: 单对象写入
- **WHEN** 调用 `write_bytes(object_path, data)` 传入字符串路径和 bytes 数据
- **THEN** 返回该对象在数据集中可持久化的 `image_uri` 字符串

#### Scenario: 批量写入
- **WHEN** 调用 `write_bytes(object_paths, data_list)` 传入列表参数
- **THEN** 返回 `StorageBatchResult` 列表，逐项记录 `ok`、`value`（image_uri）或 `error`

#### Scenario: 单个对象批量写入失败不影响整批
- **WHEN** 批量写入中某个对象写入抛出异常
- **THEN** 该对象返回 `ok=False` 和 `error` 信息，其他对象正常写入

#### Scenario: 读取不存在的对象
- **WHEN** 调用 `read_bytes` 读取一个不存在的对象
- **THEN** 抛出 `ObjectNotFoundError`

#### Scenario: 覆盖写入
- **WHEN** 调用 `write_bytes(path, data, overwrite=True)` 且对象已存在
- **THEN** 覆盖已有对象并返回 image_uri

#### Scenario: 不覆盖写入冲突
- **WHEN** 调用 `write_bytes(path, data, overwrite=False)` 且对象已存在
- **THEN** 抛出 `ObjectAlreadyExistsError`

### Requirement: FileSystemStorage 本地文件系统后端
系统 SHALL 提供 `FileSystemStorage`，通过 `connect(root)` 连接本地目录，支持在指定根目录下读写对象文件。

#### Scenario: 连接并校验可读写
- **WHEN** 调用 `connect(root)` 连接一个可读写目录
- **THEN** 创建探测文件并验证读写，成功后返回 self

#### Scenario: 连接非目录路径
- **WHEN** 调用 `connect(root)` 传入一个文件路径
- **THEN** 抛出 `StorageConnectionError`

#### Scenario: image_uri 生成
- **WHEN** 在 `FileSystemStorage` 上调用 `make_image_uri(object_path)`
- **THEN** 返回以 `file://` 为 scheme 的绝对路径 URI

### Requirement: MinioStorage MinIO 后端
系统 SHALL 提供 `MinioStorage`，通过 `connect(endpoint, access_key, secret_key, bucket)` 连接 MinIO 服务，支持在指定 bucket 下读写对象。

#### Scenario: 连接并验证 bucket
- **WHEN** 调用 `connect` 传入有效凭证
- **THEN** 验证 bucket 存在，成功后返回 self

#### Scenario: bucket 不存在
- **WHEN** 连接时 bucket 不存在
- **THEN** 抛出 `StorageConnectionError`

#### Scenario: image_uri 生成
- **WHEN** 在 `MinioStorage` 上调用 `make_image_uri(object_path)`
- **THEN** 返回 `s3://bucket/object_path` 格式的 URI

### Requirement: 批量操作辅助方法
系统 SHALL 在 `Storage` 基类上提供 `batch_write_bytes`、`batch_read_bytes`、`exists_many` 和 `delete_many` 方法，以可迭代输入逐项执行并返回 `StorageBatchResult` 列表。

#### Scenario: 批量检查存在性
- **WHEN** 调用 `exists_many(object_paths)` 传入多个路径
- **THEN** 返回每个路径的存在性检查结果列表

#### Scenario: 批量删除
- **WHEN** 调用 `delete_many(object_paths)`
- **THEN** 逐项删除并返回每项的 `ok`/`error` 结果

