## ADDED Requirements

### Requirement: ImportPipeline 导入闭环
系统 SHALL 提供 `ImportPipeline`，把外部图片来源导入受管 Storage 并生成 raw Dataset（Parquet）、import_report（JSON）和 failure_manifest（JSONL）三个标准产物。

#### Scenario: 成功导入
- **WHEN** 调用 `ImportPipeline(source, storage, output_dir).run()` 传入有效的本地目录来源
- **THEN** 返回 `ImportResult`，包含 raw_dataset_path、import_report_path、failure_manifest_path 和 report

#### Scenario: 部分失败导入
- **WHEN** 来源中部分图片文件无法读取或损坏
- **THEN** 成功的图片正常写入 storage 和 raw Dataset，失败的记录写入 failure_manifest.jsonl

#### Scenario: 空来源导入
- **WHEN** 来源目录下没有图片文件
- **THEN** 写出空 raw.parquet，import_report 中 success_count 和 failure_count 均为 0

### Requirement: SourceParser 来源扩展协议
系统 SHALL 提供 `SourceParser` Protocol，定义 `parse() -> list[SourceRecord]` 方法，支持通过实现该协议扩展新的图片来源。

#### Scenario: 本地目录解析
- **WHEN** 使用 `LocalPathParser` 解析一个包含图片的本地目录
- **THEN** 返回 SourceRecord 列表，每条包含 source_uri、source_type、source_file_name 和 local_path

#### Scenario: 自动归一化来源
- **WHEN** 向 ImportPipeline 传入字符串或 Path 作为 source
- **THEN** 自动包装为 `LocalPathParser`

#### Scenario: 自定义 SourceParser
- **WHEN** 向 ImportPipeline 传入实现了 SourceParser 协议的对象
- **THEN** 使用该对象的 parse() 方法获取来源记录

### Requirement: 基础元数据抽取
系统 SHALL 提供 `extract_basic_metadata(path)` 函数，抽取导入阶段 raw Dataset 需要的低成本基础事实，包括尺寸、格式、通道、EXIF 和 GPS 等字段。

#### Scenario: 正常图片元数据
- **WHEN** 对一个有效的 JPEG 文件调用 extract_basic_metadata
- **THEN** 返回包含 width、height、pixel_count、aspect_ratio、image_format、mime_type、image_content_hash 等字段的字典

#### Scenario: EXIF 元数据
- **WHEN** 图片包含 EXIF 数据
- **THEN** 返回 exif_orientation、exif_datetime、camera_make、camera_model、gps_present、gps_latitude、gps_longitude 字段

#### Scenario: 无 EXIF 图片
- **WHEN** 图片不含 EXIF 数据
- **THEN** EXIF 相关字段返回 None 或 False，不抛出异常

#### Scenario: 多帧图片
- **WHEN** 图片为 GIF 或多帧格式
- **THEN** 返回 animated=True 和 frame_count > 1

### Requirement: RawDatasetSchema 字段契约
系统 SHALL 提供 `RawDatasetSchema`，定义 raw Dataset 的最小必填字段列表（`required_columns`），版本属性 `version` 为 `raw.v1`，其中 `schema_version` 为数据集行中的列名。

#### Scenario: 字段列表
- **WHEN** 检查 RawDatasetSchema.required_columns
- **THEN** 包含 image_id、source_uri、source_type、source_file_name、storage_name、image_uri、file_size_bytes、image_content_hash、file_extension、mime_type、image_format、width、height、pixel_count、aspect_ratio、orientation、channels、color_mode、has_alpha、animated、frame_count、icc_profile_present、dpi_x、dpi_y、exif_orientation、exif_datetime、camera_make、camera_model、gps_present、gps_latitude、gps_longitude、import_status、imported_at、schema_version、tags

#### Scenario: schema 校验
- **WHEN** 调用 `validate_raw_dataset(dataframe)` 且 dataframe 包含所有 required_columns
- **THEN** 不抛出异常

#### Scenario: schema 校验失败
- **WHEN** 调用 `validate_raw_dataset(dataframe)` 且 dataframe 缺少必填列
- **THEN** 抛出 ValueError 列出缺失的列名

### Requirement: 日期分片存储路径
系统 SHALL 在导入时按日期和分片大小生成 raw 图片在 storage 中的分片路径。

#### Scenario: 分片路径格式
- **WHEN** 导入图片时 shard_index=1、import_date="2024-01-01"、image_id="abc"、source_file_name="img.jpg"
- **THEN** object_path 为 `images/raw/2024-01-01/shard_001/abc.jpg`

#### Scenario: 分片大小控制
- **WHEN** max_shard_size=2 且导入 3 张图片
- **THEN** 前两张在 shard_001，第三张在 shard_002
