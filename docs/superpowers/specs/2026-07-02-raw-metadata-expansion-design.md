# Raw Dataset 元数据扩展设计

## 背景

当前导入阶段只抽取少量基础字段：

```text
file_size_bytes
checksum
image_format
width
height
channels
color_mode
```

这些字段能支撑最小导入闭环，但不足以支持后续常见筛选、统计、隐私检查和来源分析。与此同时，`checksum` 字段名不如 `image_content_hash` 明确，容易与配置 hash、数据集 fingerprint、算子 hash 等概念混淆。

## 目标

1. 将 `checksum` 统一重命名为 `image_content_hash`。
2. 将本次确认的扩展字段全部纳入 raw Dataset required columns。
3. 保持导入阶段只抽取轻量事实字段，不加入清洗判断或质量评分。
4. 对 EXIF、camera、GPS、DPI、ICC 等可缺失信息使用稳定列名和可空值。
5. 图片可打开但可选元数据缺失或解析失败时，仍然导入成功。

## 非目标

1. 不新增清洗算子输出字段，例如 blur score、duplicate hash、embedding、OCR、NSFW 等。
2. 不把 EXIF 放入单独 JSON 字段。
3. 不实现导出脱敏策略，只在本设计中明确 GPS 坐标属于敏感字段。
4. 不迁移已经生成的历史 raw Dataset 文件。

## Raw Required Columns

raw Dataset required columns 更新为：

```text
image_id
source_uri
source_type
source_file_name
storage_name
image_uri
file_size_bytes
image_content_hash
file_extension
mime_type
image_format
width
height
pixel_count
aspect_ratio
orientation
channels
color_mode
has_alpha
animated
frame_count
icc_profile_present
dpi_x
dpi_y
exif_orientation
exif_datetime
camera_make
camera_model
gps_present
gps_latitude
gps_longitude
import_status
imported_at
schema_version
tags
```

## 字段语义

### 文件与格式字段

```text
file_size_bytes
image_content_hash
file_extension
mime_type
image_format
```

规则：

1. `image_content_hash` 值保持 `sha256:<hex>` 格式。
2. `file_extension` 来自文件名后缀，统一小写，例如 `.jpg`。
3. `mime_type` 优先基于文件扩展名推断，无法推断时基于 Pillow format 推断，仍无法推断时为 `None`。
4. `image_format` 继续使用 Pillow 识别到的格式，例如 `JPEG`、`PNG`。

### 图片基础字段

```text
width
height
pixel_count
aspect_ratio
orientation
channels
color_mode
has_alpha
animated
frame_count
```

规则：

1. `pixel_count = width * height`。
2. `aspect_ratio = width / height`；高度为 0 时为 `None`。
3. `orientation` 为 `landscape`、`portrait` 或 `square`。
4. `channels` 继续基于 `image.getbands()`。
5. `has_alpha` 表示图片是否有 alpha 通道或透明信息。
6. `animated` 表示是否多帧。
7. `frame_count` 静态图为 `1`，多帧图使用 Pillow `n_frames`。

### 嵌入配置与显示字段

```text
icc_profile_present
dpi_x
dpi_y
```

规则：

1. `icc_profile_present` 表示图片是否包含 ICC profile。
2. `dpi_x` 和 `dpi_y` 从 Pillow `image.info["dpi"]` 抽取。
3. DPI 缺失或格式异常时，两个字段为 `None`。

### EXIF、Camera 与 GPS 字段

```text
exif_orientation
exif_datetime
camera_make
camera_model
gps_present
gps_latitude
gps_longitude
```

规则：

1. `exif_orientation` 使用 EXIF orientation tag 的原始整数值。
2. `exif_datetime` 优先使用 `DateTimeOriginal`，其次使用 `DateTime`。
3. `camera_make` 和 `camera_model` 去除首尾空白后写入，缺失为 `None`。
4. `gps_present` 表示 EXIF 是否包含 GPS IFD。
5. `gps_latitude` 和 `gps_longitude` 使用十进制度坐标，可解析时写入 `float`，否则为 `None`。
6. GPS 坐标是敏感字段。后续对外导出时需要显式脱敏或移除，但本次不实现导出策略。

## 缺失值策略

1. required column 表示列必须存在，不表示每行必须有非空值。
2. 字符串类可选字段缺失时为 `None`。
3. 数值类可选字段缺失时为 `None`。
4. 布尔类事实字段使用明确布尔值：
   - `has_alpha`: `True` 或 `False`
   - `animated`: `True` 或 `False`
   - `icc_profile_present`: `True` 或 `False`
   - `gps_present`: `True` 或 `False`

## 错误处理

1. 图片无法被 Pillow 打开时，行为不变：进入 `failure_manifest`，`error_stage` 为 `metadata`。
2. 图片能打开但 EXIF 解析失败时，导入继续成功。
3. EXIF 解析失败只影响 EXIF/camera/GPS 字段，这些字段填 `None`，`gps_present` 按可判断结果写入；无法判断时为 `False`。
4. 扩展元数据提取不应引入网络访问、重型图像分析或清洗判断。

## 组件变更

### `src/image_gallery/importers/metadata.py`

`extract_basic_metadata()` 扩展为返回完整 raw metadata 字段：

1. 计算 `image_content_hash`。
2. 提取文件扩展名和 mime type。
3. 提取图片尺寸、比例、方向、通道、alpha、多帧、ICC、DPI。
4. 轻量解析 EXIF、camera 和 GPS。

### `src/image_gallery/schemas/raw.py`

`RawDatasetSchema.required_columns` 增加本设计列，并将 `checksum` 替换为 `image_content_hash`。

### 测试与示例

需要更新：

1. `tests/unit/importers/test_metadata.py`
2. `tests/unit/importers/test_import_pipeline.py`
3. `tests/unit/schemas/test_raw_schema.py`
4. `examples/stage1_storage_dataset_quickstart.py`
5. Notebook 等价导入验证

## 测试计划

1. metadata 单测验证基础新增字段：
   - `image_content_hash`
   - `file_extension`
   - `mime_type`
   - `pixel_count`
   - `aspect_ratio`
   - `orientation`
   - `has_alpha`
   - `animated`
   - `frame_count`
   - `icc_profile_present`
   - `dpi_x`
   - `dpi_y`
2. metadata 单测验证 EXIF/camera/GPS 字段存在，缺失时按缺失值策略返回。
3. schema 单测更新 `checksum` 为 `image_content_hash`，并覆盖新增 required columns。
4. pipeline 单测确认 raw Dataset 通过 `validate_raw_dataset()`。
5. 全量测试、ruff、mypy 通过。
6. Notebook 等价导入脚本重新运行，确认真实图片目录可生成包含新列的 raw Dataset。

## 验收标准

1. raw Dataset 不再包含 `checksum` required column，改为 `image_content_hash`。
2. 新增字段全部作为 required columns 出现在 raw Dataset 中。
3. 导入真实图片目录时成功生成 raw Dataset、import_report 和 failure_manifest。
4. EXIF/GPS 缺失不导致导入失败。
5. 图片打不开仍进入 failure manifest，不影响同批其他图片。
