## ADDED Requirements

### Requirement: Raw 元数据扩展字段清单
系统 SHALL 在导入时填充 RawDatasetSchema 的完整 33 列元数据字段，覆盖图片基础属性和 EXIF 信息。

#### Scenario: 完整字段列表
- **WHEN** ImportPipeline 完成导入
- **THEN** raw Dataset SHALL 包含以下 33 个 required 列：`image_id`、`source_uri`、`source_type`、`source_file_name`、`storage_name`、`image_uri`、`file_size_bytes`、`image_content_hash`、`file_extension`、`mime_type`、`image_format`、`width`、`height`、`pixel_count`、`aspect_ratio`、`orientation`、`channels`、`color_mode`、`has_alpha`、`animated`、`frame_count`、`icc_profile_present`、`dpi_x`、`dpi_y`、`exif_orientation`、`exif_datetime`、`camera_make`、`camera_model`、`gps_present`、`gps_latitude`、`gps_longitude`、`import_status`、`imported_at`、`schema_version`、`tags`

#### Scenario: 字段重命名
- **WHEN** 定义 hash 字段
- **THEN** 字段名 SHALL 为 `image_content_hash`（非 `checksum`），值保持 `sha256:<hex>` 格式

#### Scenario: 衍生计算字段
- **WHEN** 图片成功解码
- **THEN** SHALL 计算 `pixel_count = width * height`、`aspect_ratio = width / height`（浮点数）

### Requirement: GPS 敏感字段标记
系统 SHALL 将 GPS 坐标作为敏感字段处理，支持后续脱敏。

#### Scenario: GPS 字段定义
- **WHEN** 图片包含 EXIF GPS 信息
- **THEN** `gps_present` SHALL 为 `True`（bool），`gps_latitude`/`gps_longitude` SHALL 为十进制度浮点数

#### Scenario: GPS 解析失败
- **WHEN** EXIF GPS 解析失败
- **THEN** `gps_latitude`/`gps_longitude` SHALL 填 `None`；`gps_present` 按可判断结果写入，无法判断时 SHALL 为 `False`

#### Scenario: 脱敏预留
- **WHEN** 检查敏感字段策略
- **THEN** GPS 坐标 SHALL 被标记为敏感字段，后续导出需显式脱敏（本版不实现导出策略）

### Requirement: 元数据缺失值策略
系统 SHALL 对元数据字段缺失采用分层处理策略。

#### Scenario: Required column 语义
- **WHEN** 定义 required column
- **THEN** required column SHALL 表示列必须存在，NOT 表示每行必须非空

#### Scenario: 可选字段缺失
- **WHEN** 字符串/数值可选字段无法提取
- **THEN** SHALL 填 `None`

#### Scenario: 布尔事实字段
- **WHEN** 提取布尔事实字段（`has_alpha`、`animated`、`icc_profile_present`、`gps_present`）
- **THEN** SHALL 使用明确布尔值 `True`/`False`，NOT `None`

#### Scenario: EXIF 解析失败降级
- **WHEN** 图片能打开但 EXIF 解析失败
- **THEN** 导入 SHALL 继续成功；EXIF/camera/GPS 字段 SHALL 填 `None`

### Requirement: 导入路径分片默认参数
系统 SHALL 使用明确的分片参数控制导入图片的存储路径分布。

#### Scenario: 分片大小默认值
- **WHEN** 调用 `ImportPipeline.__init__()` 未指定 `max_shard_size`
- **THEN** SHALL 使用默认值 `max_shard_size=10000`（成功导入图片计数，失败不占位）

#### Scenario: 分片路径格式
- **WHEN** 导入图片生成存储路径
- **THEN** SHALL 使用格式 `images/raw/<yyyy-mm-dd>/shard_<index>/<image_id><extension>`，shard_index 从 `shard_001` 开始

#### Scenario: UUID 重命名
- **WHEN** 图片导入成功
- **THEN** 图片 SHALL 使用 `image_id`（UUID）重命名，保留原始扩展名（小写），NOT 暴露原始文件名

#### Scenario: 原始文件名追溯
- **WHEN** 导入图片
- **THEN** 原始文件名 SHALL 保留在 raw Dataset 的 `source_file_name` 字段中

#### Scenario: 分片大小校验
- **WHEN** `max_shard_size <= 0`
- **THEN** SHALL 抛出 `ValueError`
