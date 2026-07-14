# visualization Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: 图片网格 HTML 渲染
系统 SHALL 提供 `render_image_grid()` 函数，从 Dataset 或 DataFrame 生成适合 Notebook 展示的图片网格 HTML。

#### Scenario: 从 Dataset 渲染
- **WHEN** 传入 Dataset 对象作为 source
- **THEN** 自动调用 `to_frame()` 转换为 DataFrame 后渲染

#### Scenario: 从 DataFrame 渲染
- **WHEN** 传入 DataFrame 对象作为 source
- **THEN** 直接使用该 DataFrame 渲染

#### Scenario: 指定图片列
- **WHEN** 调用 `render_image_grid(source, image_column="image_uri")`
- **THEN** 使用指定列作为图片地址列渲染

#### Scenario: 图片列不存在
- **WHEN** image_column 不在 DataFrame 列中
- **THEN** 抛出 ValueError

#### Scenario: 说明列
- **WHEN** 调用时指定 caption_columns=["image_id", "blur_score"]
- **THEN** 每张缩略图下方显示这些列的值

#### Scenario: 默认说明列
- **WHEN** 不指定 caption_columns
- **THEN** 默认使用 image_id 列（如果存在）

#### Scenario: 缩略图宽度
- **WHEN** 调用时指定 thumbnail_width=200
- **THEN** 每张缩略图的 CSS width 为 200px

#### Scenario: 固定列数
- **WHEN** 调用时指定 columns=4
- **THEN** 网格使用 4 列 CSS grid 模板

#### Scenario: 自动列数
- **WHEN** 不指定 columns
- **THEN** 网格使用 auto-fill，最小列宽为 thumbnail_width

### Requirement: Notebook 图片网格展示
系统 SHALL 提供 `show_image_grid()` 函数，在 Notebook 环境中直接展示图片网格。

#### Scenario: IPython 环境展示
- **WHEN** 在 IPython/Jupyter 环境中调用 `show_image_grid(source)`
- **THEN** 返回 IPython HTML 对象，直接在 Notebook 中渲染

#### Scenario: 非 IPython 环境降级
- **WHEN** 在非 IPython 环境中调用 `show_image_grid(source)`
- **THEN** 返回 HTML 字符串

### Requirement: 本地路径 URI 转换
系统 SHALL 在图片网格渲染时自动将本地绝对路径转换为 `file://` URI。

#### Scenario: Windows 绝对路径
- **WHEN** image_uri 为 `C:\data\images\test.jpg` 格式的 Windows 路径
- **THEN** 转换为 `file:///C:/data/images/test.jpg` 格式的 URI

#### Scenario: 已有 scheme 的路径
- **WHEN** image_uri 已包含 scheme（如 `s3://bucket/img.jpg`）
- **THEN** 原样使用，不转换

