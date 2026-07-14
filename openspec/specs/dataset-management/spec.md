# dataset-management Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: Dataset 文件读写
系统 SHALL 提供 `Dataset` 类，支持 Parquet、CSV 和 JSONL 三种格式的文件读写。

#### Scenario: 写出 Parquet 数据集
- **WHEN** 调用 `Dataset.write(dataframe, path)` 且路径以 `.parquet` 结尾
- **THEN** 写出 Parquet 文件并返回 Dataset 对象

#### Scenario: 加载数据集
- **WHEN** 调用 `Dataset.load(path)` 传入一个有效的数据集文件路径
- **THEN** 返回 Dataset 对象，格式由文件扩展名推断

#### Scenario: 加载不存在的文件
- **WHEN** 调用 `Dataset.load(path)` 传入不存在的文件路径
- **THEN** 抛出 `FileNotFoundError`

#### Scenario: 不支持的格式
- **WHEN** 调用 `Dataset.write` 时文件扩展名不是 parquet/csv/jsonl
- **THEN** 抛出 `ValueError`

### Requirement: Dataset 数据读取与预览
系统 SHALL 在 `Dataset` 上提供 `to_frame`、`preview`、`scan`、`count` 和 `validate_readable` 方法。

#### Scenario: 读取完整 DataFrame
- **WHEN** 调用 `to_frame()`
- **THEN** 返回完整的 pandas DataFrame

#### Scenario: 按列读取
- **WHEN** 调用 `to_frame(columns=["image_id", "image_uri"])`
- **THEN** 返回只包含指定列的 DataFrame

#### Scenario: 预览前 N 行
- **WHEN** 调用 `preview(limit=10)`
- **THEN** 返回前 10 行 DataFrame

#### Scenario: 等值过滤扫描
- **WHEN** 调用 `scan(filters={"import_status": "imported"})`
- **THEN** 返回 import_status 列等于 "imported" 的行

#### Scenario: 验证可读性
- **WHEN** 调用 `validate_readable()` 且文件存在且格式有效
- **THEN** 不抛出异常

### Requirement: Dataset fingerprint
系统 SHALL 在 `Dataset` 上提供 `fingerprint()` 方法，基于数据集内容生成稳定指纹。

#### Scenario: 相同内容相同指纹
- **WHEN** 两个 Dataset 的 DataFrame 内容完全相同
- **THEN** 它们的 `fingerprint()` 返回值相同

#### Scenario: 不同内容不同指纹
- **WHEN** 两个 Dataset 的 DataFrame 内容不同
- **THEN** 它们的 `fingerprint()` 返回值不同

### Requirement: Dataset 图片 bytes 读取
系统 SHALL 在 `Dataset` 上提供 `read_image_bytes` 和 `iter_images` 方法，支持通过 `image_uri` 读取图片原始 bytes。

#### Scenario: 读取本地图片
- **WHEN** `image_uri` 为 `file://` scheme 且 Dataset 关联了正确路径
- **THEN** 返回图片文件的 bytes

#### Scenario: 读取 S3 图片
- **WHEN** `image_uri` 为 `s3://` scheme 且 Dataset 关联了 Storage
- **THEN** 通过 Storage 读取对象 bytes 并返回

#### Scenario: 缺少 Storage
- **WHEN** `image_uri` 为 `s3://` 但 Dataset 未关联 Storage
- **THEN** 抛出 `ValueError`

#### Scenario: 枚举图片对象
- **WHEN** 调用 `iter_images()`
- **THEN** 返回 `DatasetImage` 迭代器，每个包含 image_id、image_uri 和完整行数据

### Requirement: Dataset 图片网格绘制
系统 SHALL 在 `Dataset` 上提供 `draw` 方法，在 Notebook 中渲染图片网格。

#### Scenario: 默认绘制
- **WHEN** 调用 `draw()` 不传参数
- **THEN** 渲染最多 24 张图片的网格

#### Scenario: 按条件过滤绘制
- **WHEN** 调用 `draw(filter={"import_status": "imported"}, max_num=10)`
- **THEN** 只渲染符合条件的最多 10 张图片

### Requirement: Dataset 导出
系统 SHALL 提供 `DatasetExporter` 和 `DatasetLoader`，支持数据集的导出和加载。

#### Scenario: 导出为 Parquet
- **WHEN** 调用 DatasetExporter 导出为 parquet 格式
- **THEN** 写出 Parquet 文件并返回 `DatasetExportResult`

#### Scenario: 导出包含图片 bytes
- **WHEN** 导出时指定了 storage 且图片为 s3 URI
- **THEN** 图片 bytes 随导出文件一同写出

