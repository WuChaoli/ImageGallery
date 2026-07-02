# 阶段 1：Storage 开发计划

本文档用于指导阶段 1 中 Storage 模块的开发顺序。Storage 是公共基础能力，只负责后端存储库接入、对象读写、image_uri 生成和受管输出路径校验，不实现 Dataset、图片导入、清洗平台、artifact manifest 或运行状态恢复。

## 1. 设计依据

1. `docs/development/图片数据集处理框架-顶层开发计划.md`
2. `docs/architecture/modules/存储系统.md`
3. `docs/architecture/图片数据集处理框架-总体架构.md`
4. `docs/architecture/modules/图片导入与元数据.md`
5. `docs/architecture/modules/数据集管理与可视化.md`

## 2. 开发目标

Storage 模块第一版要提供稳定、可测试、可被后续模块复用的存储访问底座：

1. 支持具名存储库注册。
2. 支持单个 Storage 实例连接单个后端库，并允许调用方按名称选择存储库。
3. 支持本地文件系统存储库。
4. 为 MinIO 存储库预留 MinioStorage 边界，并按依赖可用性实现最小读写能力。
5. 支持 object_path 规范化和受管输出路径校验。
6. 支持对象写入、读取、存在性判断和 image_uri 生成。

## 3. 非目标

Storage 阶段不做以下内容：

1. 不生成 raw、clean、dropped、full Dataset。
2. 不实现 Parquet Dataset 读写。
3. 不扫描外部图片来源。
4. 不提取图片元数据。
5. 不实现 CleaningRecipe、ExecutionPlan、ExecutionPack。
6. 不定义 node_result、node_status_matrix 或 merge_result。
7. 不实现 artifact manifest、resume、rerun 或 SQLite Run State Store。
8. 不实现复杂权限、多租户、跨区域复制和生命周期治理。

## 4. 模块边界

Storage 对上层模块提供统一对象访问能力。上层模块传入 storage_name 和 object_path，或传入当前环境可访问的 image_uri，不直接依赖 MinIO SDK 细节。

Storage 负责：

1. 管理 `storage_name` 到单个后端存储库实例的映射。
2. 根据 storage_name 和 object_path 生成 image_uri。
3. 通过 `StorageRegistry.connect(storage_name)` 返回已连接的 Storage 实例。
4. 通过 Storage 实例方法读写对象。
5. 解析当前运行环境下可访问的 image_uri。
6. 校验 object_path 和 output URI 是否属于受管范围。

Storage 不负责：

1. 判断对象是不是图片。
2. 判断对象属于哪个 Dataset 阶段。
3. 决定对象是否进入 clean 或 dropped。
4. 维护清洗任务状态。
5. 校验 artifact manifest 的业务完整性。

## 5. 建议代码位置

```text
src/image_gallery/storage/
  __init__.py
  config.py
  uri.py
  registry.py
  base.py
  filesystem.py
  minio.py
  errors.py
```

测试建议放在：

```text
tests/unit/storage/
tests/integration/storage/
```

## 6. 核心对象

### 6.1 StorageConfig

用于描述全部存储库配置。

建议包含：

```text
default_storage
storages
```

其中每个 storage 至少包含：

```text
name
type
root 或 endpoint/bucket
```

其中 name 就是调用方使用的 storage_name。每个实例只连接一个文件系统根目录或一个 MinIO bucket。

### 6.2 StorageRegistry

负责注册和查找具名存储库。

最小能力：

1. 根据 `storage_name` 查找 storage 配置。
2. 返回默认 storage。
3. 校验 storage 是否存在。
4. 从 Python dict 创建 registry。
5. 通过 `connect(storage_name=None)` 返回已连接的 Storage 实例。

### 6.3 ImageUri

负责生成和规范化图片主地址。

第一版本地文件系统推荐使用绝对路径或 file URI：

```text
/data/image_gallery/project_a/storage/images/a.jpg
file:///data/image_gallery/project_a/storage/images/a.jpg
```

最小能力：

1. 把文件系统 object_path 解析为 storage root 下的绝对地址。
2. 拒绝空 storage_name、空 object_path 和不安全路径。
3. 判断 image_uri 是否属于已注册 storage。
4. 不要求支持 `platform://` 地址。

### 6.4 Storage

所有后端存储库的抽象基类，表示一个已经连接到单个后端库的存储库实例。

最小能力：

```text
connect() -> Storage
write_bytes(object_path, data, overwrite=False) -> image_uri
read_bytes(object_path) -> bytes
exists(object_path) -> bool
delete(object_path) -> None
copy(src_object_path, dst_object_path, overwrite=False) -> image_uri
move(src_object_path, dst_object_path, overwrite=False) -> image_uri
make_image_uri(object_path) -> str
```

批量能力由抽象基类提供默认实现：

```text
write_many(items, overwrite=False)
read_many(object_paths)
exists_many(object_paths)
delete_many(object_paths)
```

批量操作第一版可以先用单对象方法循环实现，但返回值必须保留每个对象的成功、失败和错误信息，避免单个对象失败中断整批导入。

第一版可以先用 bytes 接口打通链路；后续按需要增加 stream、open_reader、open_writer。

### 6.5 FileSystemStorage

本地文件系统后端。

最小能力：

1. 把 object_path 映射到 storage root 下的真实路径。
2. 写入 bytes。
3. 读取 bytes。
4. 判断对象是否存在。
5. 删除对象。
6. 复制和移动对象。
7. 生成绝对路径或 `file://` 形式的 image_uri。

### 6.6 MinioStorage

MinIO 后端。

最小能力：

1. 通过 bucket 和 object_path 读写对象。
2. 判断对象是否存在。
3. 删除对象。
4. 复制和移动对象。
5. 生成当前环境可访问的 image_uri 或 presigned URL。

如果开发环境暂时没有 MinIO 依赖，先保留 MinioStorage 边界和跳过式集成测试，不阻塞文件系统后端验收。

## 7. 开发顺序

### 步骤 1：地址模型

实现 `ImageUri` 的生成、规范化和基础校验。

验证：

1. 可以把 `local_main` + `images/a.jpg` 生成 storage root 下的绝对 image_uri。
2. 空 storage_name、空 object_path 会被拒绝。
3. object_path 规范化后不能逃逸 storage root。
4. 已生成的 image_uri 可以被判断为属于对应 storage。

### 步骤 2：错误类型

定义 Storage 模块自己的异常类型。

建议错误类型：

1. `StorageError`
2. `InvalidStorageUriError`
3. `StorageNotFoundError`
4. `UnsafeStoragePathError`
5. `ObjectAlreadyExistsError`
6. `ObjectNotFoundError`

验证：

1. 调用方可以区分 URI 错误、storage 错误和对象不存在错误。
2. 错误信息包含 storage_name、object_path 或 URI 等关键上下文。

### 步骤 3：Storage 抽象基类

实现 Storage 抽象基类和批量操作默认实现。

验证：

1. 抽象类定义 connect、write_bytes、read_bytes、exists、delete、copy、move 和 make_image_uri。
2. 批量操作会逐项调用单对象方法。
3. 批量操作中单项失败不会中断整批结果汇总。

### 步骤 4：StorageRegistry

实现具名 storage 注册、配置查找和连接入口。

验证：

1. 可以从 dict 配置创建 registry。
2. 可以获取默认 storage。
3. 未注册 storage 会被明确拒绝。
4. 不支持的 storage type 会被明确拒绝。
5. `connect(storage_name)` 会根据 storage type 返回已连接的具体 Storage 实例。
6. `connect()` 未传 storage_name 时使用 default_storage。

### 步骤 5：FileSystemStorage

实现本地文件系统读写能力。

验证：

1. 写入对象后可以读取同样的 bytes。
2. `exists` 能正确反映对象状态。
3. 默认不覆盖已有对象。
4. `overwrite=True` 时可以覆盖已有对象。
5. `..`、绝对路径、符号链接逃逸会被拒绝。
6. copy 和 move 能返回目标对象 image_uri。

### 步骤 6：MinioStorage 边界

实现或预留 MinioStorage。

验证：

1. 没有 MinIO 依赖时，单元测试不失败。
2. 有 MinIO 测试环境时，可以执行最小读写集成测试。
3. 上层调用不需要感知 MinIO SDK。
4. MinIO 的 copy 和 move 与 Storage 抽象接口一致。

### 步骤 7：文档与示例

补充最小使用示例。

示例应覆盖：

1. 注册本地 storage。
2. 通过 `registry.connect("local_main")` 获取 Storage 实例。
3. 写入对象并得到 image_uri。
4. 通过 Storage 实例读取对象。
5. 指定不同 storage_name 写入不同后端库。

## 8. 验收标准

Storage 模块完成时应满足：

1. 可以注册 `local_main` 文件系统 storage。
2. 可以通过 `StorageRegistry.connect(storage_name)` 选择不同后端存储库。
3. 可以写入、读取、判断存在和删除对象。
4. 可以复制和移动对象。
5. 可以执行批量读写、批量存在性判断和批量删除，并保留逐项结果。
6. 可以生成当前环境下可直接访问的 image_uri。
7. 可以拒绝未注册 storage。
8. 可以拒绝路径逃逸和非受管输出路径。
9. 可以保证默认不覆盖已有对象。
10. 单元测试覆盖 URI、registry、Storage 抽象、filesystem storage 和安全路径校验。
11. 不包含 Dataset、清洗平台、artifact manifest 或 SQLite state 的实现。

## 9. 后续衔接

Storage 完成后，后续模块按以下方式复用：

1. Dataset 模块通过 Storage 读写 Parquet 文件。
2. 图片导入模块通过 Storage 写入图片对象，并把返回的 `image_uri` 写入 raw Dataset。
3. 可视化模块通过 `image_uri` 直接读取或展示图片。
4. 清洗平台通过 Storage 读取图片和写入后续清洗产物，但清洗产物的 schema、manifest 和恢复语义由清洗平台与错误恢复模块定义。
