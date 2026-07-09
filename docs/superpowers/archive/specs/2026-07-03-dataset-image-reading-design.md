# Dataset 图片读取与 Cleaner 适配设计

## 目标

让 `Dataset` 成为图片内容读取的统一入口，使 `BasicCleaner` 和内置 backend 可以处理本地绝对路径、`file://` 地址以及 MinIO/S3 风格的 `s3://bucket/object_path` 地址。

完成后，包含远端 `image_uri` 的 Dataset 不需要先在 Notebook 中 materialize 到本地 cache，基础算子也不再直接把 `image_uri` 当成本地路径读取。

## 非目标

1. 不引入多 storage 自动路由或全局 `StorageRegistry`。
2. 不支持 HTTP、HTTPS、OSS、COS 等额外远端地址。
3. 不改变 Dataset 的 durable schema；`image_uri` 仍然是唯一图片主引用。
4. 不要求 fastdup backend 在本次实现真实支持远端对象。
5. 不让 `BasicCleaner` 预先读取全部图片或把图片内容缓存到内存。

## 核心设计

`Dataset` 增加可选的 `storage` 依赖：

```python
Dataset.from_path(dataset_path, storage=None)
Dataset.write(data, output_path, storage=None)
```

`Dataset` 内置轻量 `image_uri_parser`，第一版只判定两类地址：

1. 本地地址：绝对路径或 `file://...`。
2. 远端对象地址：`s3://bucket/object_path`，按 MinIO/S3 对象路径语义读取。

本地地址由 Dataset 直接读取文件。`s3://...` 地址由 Dataset 解析出 `bucket` 和 `object_path`，再委托绑定的 `Storage` 读取对象 bytes。没有绑定 storage 时，读取 `s3://...` 必须抛出明确错误。

## Dataset 图片 API

新增读取方法：

```python
dataset.read_image_bytes(image_uri: str) -> bytes
dataset.read_image(image_uri: str) -> PIL.Image.Image
dataset.read_image_bytes_batch(image_uris: Iterable[str]) -> list[DatasetImageBytesReadResult]
dataset.read_image_batch(image_uris: Iterable[str]) -> list[DatasetImageReadResult]
dataset.iter_images(columns: list[str] | None = None) -> Iterator[DatasetImage]
```

`read_image_bytes()` 只负责读取 bytes，不校验图片格式。`read_image()` 基于 bytes 使用 Pillow 解码，并调用 `load()`，确保返回对象脱离底层 stream 后仍可使用。

批量方法逐项返回结果，单张失败不影响整批：

```python
@dataclass(frozen=True)
class DatasetImageBytesReadResult:
    image_uri: str
    ok: bool
    data: bytes | None = None
    error: str | None = None


@dataclass(frozen=True)
class DatasetImageReadResult:
    image_uri: str
    ok: bool
    image: PIL.Image.Image | None = None
    error: str | None = None
```

## 可枚举图片对象

`Dataset.iter_images()` 按 Dataset 当前行顺序返回 `DatasetImage`：

```python
@dataclass(frozen=True)
class DatasetImage:
    image_id: str
    image_uri: str
    row: dict[str, object]
    dataset: Dataset

    def read_bytes(self) -> bytes: ...
    def read_image(self) -> PIL.Image.Image: ...
```

`DatasetImage` 是 backend 使用的主要入口。它保留 `image_id`、`image_uri` 和原始行字段，同时把读取行为委托回所属 Dataset。

## Cleaner 与 Backend 适配

`BasicCleaner` 主流程保持不变。它已经把 `Dataset` 传入 `backend.compute_parameters(...)`，后续仍只负责调度、backend 分组、状态记录和表写出。

需要升级的是 backend 契约语义：

```python
compute_parameters(dataset, parameter_table, requests, artifacts_dir)
```

如果 backend 需要图片内容，必须通过 `dataset.iter_images()`、`DatasetImage.read_bytes()` 或 `DatasetImage.read_image()` 获取，不再直接调用 `file_image_uri_to_path()` 或把 `image_uri` 传给只能读取本地路径的 API。

内置 backend 改造范围：

1. `PillowMetadataBackend`：通过 `DatasetImage.read_image()` 读取图片并计算宽高、格式和 decode 状态。
2. `OpenCVQualityBackend`：通过 `DatasetImage.read_image()` 得到 PIL 图片，再转换为灰度数组；blur 可在 NumPy 数组上调用 OpenCV Laplacian。
3. `ImageHashBackend`：`content_hash` 使用 `DatasetImage.read_bytes()`，`phash` 使用 `DatasetImage.read_image()`。
4. `FastdupSimilarityBackend`：本次仍保持未实现或依赖错误。后续如需支持远端对象，应在 backend 内部基于 Dataset materialize 到 `artifacts_dir`，而不是要求调用方提前缓存。

## 错误处理

单张读取方法失败时直接抛错，便于 backend 把失败转成自身语义。

批量读取方法记录失败项：

1. 本地路径不存在：记录或抛出 `FileNotFoundError`。
2. `s3://...` 但 Dataset 未绑定 storage：错误信息包含 `storage is required for s3 image_uri`。
3. `s3://...` 地址缺少 bucket 或 object_path：抛出明确的 Dataset 图片 URI 错误。
4. Storage 读取失败：保留 storage 原始错误信息。
5. Pillow 解码失败：`read_image()` 抛错；`read_image_batch()` 记录失败项。
6. 不支持的 scheme：抛出明确错误，不静默兜底。

## 测试范围

Dataset 单元测试：

1. 本地绝对路径读取 bytes 和 PIL 图片。
2. `file://` 地址读取 bytes 和 PIL 图片。
3. `s3://bucket/object_path` 通过 fake storage 读取。
4. `s3://...` 未绑定 storage 时失败信息明确。
5. `read_image_bytes_batch()` 和 `read_image_batch()` 支持部分失败。
6. `iter_images()` 按 Dataset 行顺序返回 `DatasetImage`。

Backend 单元测试：

1. Pillow metadata backend 可处理 fake storage 提供的 `s3://...` 图片。
2. OpenCV quality backend 可处理 fake storage 提供的 `s3://...` 图片。
3. Image hash backend 可处理 fake storage 提供的 `s3://...` 图片。
4. 现有本地路径测试继续通过。

集成测试：

1. `BasicCleaner` 输入绑定 fake storage 的 `s3://...` Dataset，可以跑通基础内置算子。
2. `parameter_table` 和 `evaluation_table` 继续生成既有字段。
3. Cleaner 不需要在主流程中预读或缓存图片。

## 成功标准

1. `Dataset` 可以统一读取本地路径、`file://` 和 `s3://...` 图片。
2. `Dataset.iter_images()` 可以按顺序枚举图片对象。
3. Pillow、OpenCV 和 hash backend 不再依赖本地路径读取图片内容。
4. `BasicCleaner` 能处理绑定 storage 的远端 Dataset。
5. 现有本地 Dataset、quickstart 和算子测试保持兼容。
