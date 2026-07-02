# Importer MinIO Notebook 验证设计

## 背景

当前已经有两个相关验证入口：

1. `notebooks/importers_local_directory_test.ipynb`：验证本地图片目录导入到本地文件系统受管库。
2. `notebooks/minio_test.ipynb`：验证 MinIO storage 的连接和基本读写能力。

本次需要继续验证 importer 在 MinIO 目标 storage 下的行为。当前 importer 的 source reader 仍以本地路径为输入，MinIO 在这次验证中只作为受管图片库目标，不作为源端 reader。

## 目标

1. 新增独立 notebook：`notebooks/importers_minio_test.ipynb`。
2. 复用当前本地图片源：

```text
/mnt/c/Users/wuchaoli/Pictures/测试图片
```

如 WSL 路径不存在，再回退到 Windows 风格路径：

```text
C:\Users\wuchaoli\Pictures\测试图片
```

3. MinIO 连接参数从仓库根目录 `.env` 读取，不在 notebook 中硬编码密钥。
4. 使用 `LocalDirectoryReader` 读取本地图片，并通过 `ImportPipeline` 写入 `MinioStorage`。
5. 输出 importer 产物到：

```text
notebooks/.importers_test_library/minio_outputs/
```

6. 验证 raw dataset 中的 `image_uri` 指向 MinIO 对象，并符合当前日期分片和 UUID 文件名规则。
7. 抽样回读 MinIO 对象，确认 raw dataset 中记录的对象真实存在且可读取。

## 非目标

1. 不实现 MinIO source reader。
2. 不修改 `ImportPipeline` 行为。
3. 不新增自动化集成测试。
4. 不覆盖 `notebooks/.importers_test_library/outputs/` 中现有本地文件系统 importer 产物。
5. 不在 notebook 或文档中写入 MinIO 密钥明文。

## Notebook 结构

### 1. 环境与输入准备

第一组 cell 负责：

1. 定位仓库根目录。
2. 使用 `python-dotenv` 加载 `.env`。
3. 读取以下环境变量：

```text
IMAGE_GALLERY_MINIO_ENDPOINT
IMAGE_GALLERY_MINIO_ACCESS_KEY
IMAGE_GALLERY_MINIO_SECRET_KEY
IMAGE_GALLERY_MINIO_BUCKET
```

4. 解析 endpoint URL，得到 MinIO SDK 需要的 `endpoint` 和 `secure`。
5. 选择图片源目录并用 `LocalDirectoryReader` 生成 records。
6. 打印 source dir、bucket、records 数量和输出目录。

### 2. MinIO Storage 连接

第二组 cell 创建 `MinioStorage(storage_name="minio_test_picture_library")`，并调用显式 `connect(...)` 参数连接 MinIO。

连接失败时直接让 notebook cell 抛错，便于定位是 `.env`、bucket、网络还是服务问题。

### 3. ImportPipeline 导入

第三组 cell 执行：

```python
ImportPipeline(
    storage=storage,
    output_dir=library_root / "minio_outputs",
    global_tags=["dataset/test_pictures", "source/windows_pictures", "storage/minio"],
).run(records)
```

导入完成后打印：

1. `raw_dataset_path`
2. `import_report_path`
3. `failure_manifest_path`
4. `report`

### 4. Raw Dataset 验证

第四组 cell 读取 raw parquet，并检查：

1. `image_uri` 全部以 `s3://<bucket>/images/raw/` 开头。
2. `image_uri` 包含当天日期和 `shard_001` 等分片路径。
3. 受管文件名是 UUID 加原始小写扩展名，不暴露 `source_file_name`。
4. `storage_name` 全部等于 `minio_test_picture_library`。
5. `source_file_name` 仍保留原始文件名。

### 5. MinIO 对象抽样回读

第五组 cell 从 raw dataset 抽样若干行，将 `s3://<bucket>/<object_path>` 转换为 `object_path`，并调用：

```python
storage.read_bytes(object_path)
```

验证对象可读取且返回内容非空。抽样数量保持较小，例如最多 5 张，避免 notebook 手工验证过慢。

### 6. 结果预览

最后可复用当前 dataset preview 展示字段，优先展示：

1. `source_file_name`
2. `image_uri`
3. `image_format`
4. `width`
5. `height`
6. `file_size_bytes`

由于 `image_uri` 是 `s3://`，当前 notebook 图片网格不要求直接渲染 MinIO 图片，避免引入 presigned URL 或临时下载逻辑。

## 错误处理

1. `.env` 缺少必要变量时，明确抛出 `RuntimeError` 并指出变量名。
2. MinIO bucket 不存在或连接失败时，复用 `MinioStorage.connect()` 的错误。
3. 单张图片元数据解析或写入失败时，继续复用 `ImportPipeline` 的 `failure_manifest` 机制。
4. 抽样回读失败时，让验证 cell 抛错，表示 raw dataset 中存在不可读的 MinIO 对象。

## 验收标准

1. 新增 `notebooks/importers_minio_test.ipynb`。
2. notebook 能从本地测试图片目录导入到 MinIO bucket。
3. `notebooks/.importers_test_library/minio_outputs/raw.parquet` 存在并包含成功导入记录。
4. `image_uri` 使用 `s3://<bucket>/images/raw/<yyyy-mm-dd>/shard_xxx/<uuid>.<ext>` 格式。
5. raw dataset 中的 MinIO 对象可通过 `storage.read_bytes(object_path)` 抽样回读。
6. 现有本地 importer notebook 和输出目录不被覆盖。
