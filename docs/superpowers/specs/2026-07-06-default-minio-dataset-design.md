# 默认 MinIO 测试数据集构建设计

## 背景

项目后续需要一批稳定可复用的真实图片数据，用于 Notebook、导入链路、清洗链路和算子验证。源图片来自 Windows 图片目录：

```text
C:\Users\wuchaoli\Pictures\5月22日小车采集图（原始数据）
```

在当前 WSL 环境中对应路径为：

```text
/mnt/c/Users/wuchaoli/Pictures/5月22日小车采集图（原始数据）
```

当前仓库已经具备本地目录导入、MinIO storage 写入、raw Dataset 生成和 `.env` 加载 MinIO 配置的基础能力。本设计只定义默认测试数据集的构建入口和产物约定，不改变 importer、storage、cleaning 或 operator 的公共行为。

## 目标

1. 新增专用 Notebook：`notebooks/default_minio_dataset_build.ipynb`。
2. 将源目录中的图片全量导入 MinIO，并生成 full raw Dataset。
3. 从 full raw Dataset 中使用固定随机种子抽样 1000 张，生成 sample raw Dataset。
4. 后续默认轻量测试优先使用 sample，完整验证或性能验证使用 full。
5. MinIO 对象使用 importer 当前默认日期分片路径，不引入稳定业务前缀。

## 非目标

1. 不新增公共 Python API。
2. 不修改 `ImportPipeline`、`MinioStorage`、`Dataset`、cleaning 或 operator 实现。
3. 不把图片或生成的 Parquet 数据提交到 Git。
4. 不清空、覆盖或迁移 MinIO 中已有对象。
5. 不实现 MinIO 源端 reader。
6. 不把 MinIO 密钥写入 Notebook、文档或代码。

## 产物约定

Notebook 路径：

```text
notebooks/default_minio_dataset_build.ipynb
```

全量数据集输出目录：

```text
notebooks/.importers_test_library/default_minio_dataset/full/
```

全量 raw Dataset：

```text
notebooks/.importers_test_library/default_minio_dataset/full/raw.parquet
```

1000 张测试子集输出目录：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/
```

1000 张测试子集 raw Dataset：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
```

抽样配置：

```text
sample_size = 1000
random_state = 20260706
```

`sample_1000/raw.parquet` 是 full raw Dataset 的派生子集，不会重复上传图片。它保留 full 中的 `image_id`、`source_uri`、`image_uri`、metadata、`tags` 等字段，后续读取图片时继续通过 full 导入阶段写入的 MinIO 对象访问。

## 数据流

1. Notebook 定位仓库根目录。
2. 使用 `python-dotenv` 读取仓库根目录 `.env`。
3. 读取以下 MinIO 环境变量：

```text
IMAGE_GALLERY_MINIO_ENDPOINT
IMAGE_GALLERY_MINIO_ACCESS_KEY
IMAGE_GALLERY_MINIO_SECRET_KEY
IMAGE_GALLERY_MINIO_BUCKET
```

4. 解析 endpoint，得到 MinIO SDK 需要的 `endpoint` 和 `secure`。
5. 选择源目录，优先使用 WSL 路径：

```text
/mnt/c/Users/wuchaoli/Pictures/5月22日小车采集图（原始数据）
```

6. 创建并连接：

```python
MinioStorage(storage_name="default_minio_test_dataset")
```

7. 调用现有 importer：

```python
ImportPipeline(
    source=source_dir,
    storage=storage,
    output_dir=full_dir,
    global_tags=[
        "dataset/default_minio",
        "dataset/full",
        "source/windows_pictures",
        "source/vehicle_20240522",
        "storage/minio",
    ],
).run()
```

8. importer 使用默认 prefix，生成类似以下格式的 MinIO 对象：

```text
s3://<bucket>/images/raw/<yyyy-mm-dd>/shard_xxx/<uuid>.<ext>
```

9. 读取 full 的 `raw.parquet`。
10. 使用 `sample(n=1000, random_state=20260706)` 生成 sample dataframe。
11. 将 sample dataframe 写入 `sample_1000/raw.parquet`。
12. 为 sample 写出轻量 `import_report.json`，说明它是 full 的派生子集，并记录 `sample_size`、`random_state`、`source_raw_dataset_path` 和 `source_row_count`。

## Notebook 输出信息

Notebook 应显式打印以下信息，方便人工确认：

1. 源目录。
2. 源目录可识别图片数。
3. MinIO bucket。
4. full raw Dataset 路径。
5. sample raw Dataset 路径。
6. full import report。
7. sample size。
8. random seed。
9. 抽样回读验证结果。

## 错误处理

1. `.env` 缺少必要变量时，直接抛出包含变量名的 `RuntimeError`。
2. 源目录不存在时直接失败。
3. 源目录中可识别图片少于 1000 张时直接失败，不生成 sample。
4. MinIO 连接失败时沿用 `MinioStorage.connect()` 的错误。
5. 单张图片导入失败时沿用 `ImportPipeline` 的 `failure_manifest.jsonl`。
6. sample 派生前要求 full 至少有 1000 条成功记录。
7. sample 派生后校验 `image_id` 全部来自 full，且 `image_uri` 非空。
8. 抽样回读 MinIO 对象时，最多检查 10 张；任意对象不可读或返回空 bytes 时直接失败。

## 验证标准

1. `notebooks/default_minio_dataset_build.ipynb` 存在。
2. 运行后 full raw Dataset 存在：

```text
notebooks/.importers_test_library/default_minio_dataset/full/raw.parquet
```

3. 运行后 sample raw Dataset 存在：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
```

4. full 成功记录数等于 importer report 中的 `success_count`。
5. sample 恰好 1000 行。
6. sample 使用 `random_state=20260706`，重复运行可得到同一批 `image_id`。
7. full 和 sample 的 `image_uri` 都以 `s3://<bucket>/images/raw/` 开头。
8. full 和 sample 的 `image_uri` 都包含运行日期分片路径。
9. 抽样 MinIO 对象可通过 `storage.read_bytes(object_path)` 读取到非空 bytes。
10. 现有 cleaning/operator 代码不被修改。
11. 现有 importer Notebook 产物不被覆盖。

## 后续默认使用方式

后续 Notebook 或测试需要轻量默认数据时，优先读取：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
```

需要完整真实数据验证时，读取：

```text
notebooks/.importers_test_library/default_minio_dataset/full/raw.parquet
```

读取 MinIO 图片时应使用 `Dataset.from_path(..., storage=minio_storage)`，并复用 `.env` 中的 MinIO 配置连接 storage。
