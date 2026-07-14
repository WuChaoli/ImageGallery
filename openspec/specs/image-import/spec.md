# image-import Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
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

### Requirement: URL 导入安全边界（PLANNED）
系统 SHALL 在 URL 导入模式下强制执行安全边界检查，拒绝不安全的来源地址。

#### Scenario: 拒绝内网地址
- **WHEN** URL 导入请求指向 localhost、127.0.0.1、10.x.x.x、192.168.x.x 或链路本地地址
- **THEN** 拒绝导入并抛出 SecurityError

#### Scenario: 拒绝云元数据地址
- **WHEN** URL 指向 169.254.169.254（AWS/GCP/Azure 实例元数据）
- **THEN** 拒绝导入并抛出 SecurityError

#### Scenario: 限制重定向
- **WHEN** URL 响应包含重定向且重定向次数超过限制
- **THEN** 中止下载并记录失败

#### Scenario: 限制文件大小
- **WHEN** URL 响应的 Content-Length 超过配置的最大文件大小
- **THEN** 中止下载并记录失败

#### Scenario: 校验 Content-Type
- **WHEN** URL 响应的 Content-Type 不是图片 MIME 类型
- **THEN** 跳过该 URL 并记录在 failure_manifest 中

#### Scenario: 仅允许 HTTP/HTTPS
- **WHEN** URL 的 scheme 不是 http 或 https
- **THEN** 拒绝导入并抛出 ValueError

### Requirement: 导入模式策略（PLANNED）
系统 SHALL 支持三种导入模式，控制图片文件在导入时的物理复制行为。

#### Scenario: copy 模式
- **WHEN** 导入模式为 copy
- **THEN** 将图片文件复制到平台受管存储，image_uri 指向受管存储地址

#### Scenario: reference 模式
- **WHEN** 导入模式为 reference
- **THEN** 仅在 raw Dataset 中登记已有对象的地址，不执行物理复制，image_uri 指向原始地址

#### Scenario: copy_on_write 模式
- **WHEN** 导入模式为 copy_on_write
- **THEN** 初始导入时只登记引用，在清洗或导出需要时才复制到受管存储

#### Scenario: 默认模式为 copy
- **WHEN** 未显式指定导入模式
- **THEN** 使用 copy 模式

#### Scenario: 导入幂等键
- **WHEN** 同一图片被重复导入
- **THEN** 基于 source_uri + image_content_hash + import_run_id 生成幂等键，避免重复写入

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

