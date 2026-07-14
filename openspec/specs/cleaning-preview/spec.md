# cleaning-preview Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: apply_final_action 归并策略
系统 SHALL 提供 `apply_final_action()` 函数，基于 evaluation_table 中各算子的 action 列和 operator_outputs 映射，生成 final_action、final_reason 和 triggered_operator_names 列。

#### Scenario: 无算子触发
- **WHEN** 某行所有算子的 action 均为 "keep"
- **THEN** 该行 final_action 为 "keep"，final_reason 为空，triggered_operator_names 为空

#### Scenario: 单算子触发
- **WHEN** 某行只有 quality.blur_check 的 action 为 "review"
- **THEN** final_action 为 "review"，final_reason 包含 blur_reason，triggered_operator_names 为 "quality.blur_check"

#### Scenario: 多算子冲突取最高优先级
- **WHEN** 某行同时有 "review" 和 "drop" 两种 action
- **THEN** final_action 为 "drop"（优先级高于 review）

#### Scenario: action 优先级
- **WHEN** 检查 ACTION_PRIORITY 映射
- **THEN** keep < review < drop < restricted

### Requirement: build_preview 预览摘要
系统 SHALL 提供 `build_preview()` 函数，基于 evaluation_table 和 operator_outputs 构造预览摘要。

#### Scenario: 预览统计
- **WHEN** 调用 `build_preview(evaluation_table, operator_outputs)`
- **THEN** 返回 PreviewResult，包含 total_count、clean_count、review_count、dropped_count 和 restricted_count

#### Scenario: 预览采样行
- **WHEN** 调用 `build_preview(evaluation_table, operator_outputs, limit=20)`
- **THEN** sample_rows 包含前 20 行带 final_action 的 DataFrame

#### Scenario: 算子摘要
- **WHEN** 检查 PreviewResult.operator_summary
- **THEN** 包含各算子的触发计数统计

### Requirement: HTML 预览生成
系统 SHALL 提供 `write_preview_html()` 函数，生成包含缩略图的静态 HTML 预览文件。

#### Scenario: 按算子生成预览
- **WHEN** 调用 `write_preview_html` 指定 operator_name
- **THEN** 使用该算子的 PreviewPolicy 配置生成预览 HTML

#### Scenario: 按 action 过滤
- **WHEN** 调用 `write_preview_html` 指定 action="drop"
- **THEN** 只包含 final_action 为 drop 的图片

#### Scenario: 分组预览
- **WHEN** 调用 `write_preview_html` 指定 groupby="perceptual_duplicate_group_id"
- **THEN** 按分组展示图片，每组最多 max_items_per_group 张

#### Scenario: 内联缩略图
- **WHEN** 生成 HTML 预览且 Dataset 关联了 Storage
- **THEN** 图片以 base64 内联方式嵌入 HTML

### Requirement: PreviewPolicy 算子级预览策略
系统 SHALL 提供 `PreviewPolicy`，描述每个算子在预览中的默认 action 过滤、分组字段、排序字段和说明列。

#### Scenario: 默认策略
- **WHEN** 创建 OperatorSpec 时不指定 preview_policy
- **THEN** 使用 PreviewPolicy 默认值（default_actions=[]，caption_columns=[]）

#### Scenario: 内置算子预览策略
- **WHEN** 检查 _to_builtin_preview_spec 函数返回的算子
- **THEN** 每个内置算子都有定制的 PreviewPolicy（如 duplicate 类算子设置 groupby 和 include_group_context）

#### Scenario: 预览策略解析
- **WHEN** 调用 `resolve_preview_policy(configured_operator, node_policy)`
- **THEN** 合并算子级 PreviewPolicy 和节点级策略

### Requirement: export("ALL") 批量导出（PLANNED）
系统 SHALL 支持 `result.export("ALL", output_dir)` 一次导出所有数据集视图。

#### Scenario: 批量导出四个数据集
- **WHEN** 调用 `result.export("ALL", output_dir)`
- **THEN** 在 output_dir 下生成 full.parquet、clean.parquet、review.parquet、dropped.parquet 四个文件

#### Scenario: 默认列与输入一致
- **WHEN** 导出数据集且未指定 include_columns
- **THEN** 导出列与输入 raw Dataset 列保持一致

#### Scenario: 计算列需显式选择
- **WHEN** 导出时指定 `include_columns=["blur_score", "blur_action"]`
- **THEN** 导出数据集包含输入列加上 blur_score 和 blur_action 列

#### Scenario: 导出返回 Dataset
- **WHEN** 调用 `result.export("clean", path)`
- **THEN** 返回 Dataset 对象指向导出的 parquet 文件

### Requirement: 导出默认列契约（PLANNED）
系统 SHALL 确保导出结果的列契约与用户预期一致。

#### Scenario: 不暴露内部计算列
- **WHEN** 导出 clean 数据集且未显式请求计算列
- **THEN** 不包含 blur_score、exact_duplicate_group_id 等内部计算中间列

#### Scenario: final_action 列默认包含
- **WHEN** 导出任何数据集
- **THEN** final_action 和 final_reason 列默认包含在导出中

### Requirement: 逐算子 drop/review 预览（PLANNED）
系统 SHALL 支持为每个逻辑算子独立导出仅包含 drop 和 review 命中行的 HTML 预览。

#### Scenario: 逐算子预览 API
- **WHEN** 调用 `CleanerResult.preview_html(path, operator_name="quality.blur_check", actions=["drop", "review"])`
- **THEN** SHALL 仅导出该算子的 drop + review 命中行，NOT 使用 `actions="full"`

#### Scenario: Action 过滤来源
- **WHEN** 生成逐算子预览
- **THEN** SHALL 从 `evaluation_frame` 读取该算子的 `*_action` 列进行过滤

#### Scenario: 命中统计验证
- **WHEN** 验证逐算子预览结果
- **THEN** HTML 的 rows 数 SHALL 等于该算子的 `drop_count + review_count`

#### Scenario: Notebook 汇总表
- **WHEN** Notebook 展示逐算子预览汇总
- **THEN** SHALL 包含 `drop_count`、`review_count`、`preview_count`、`preview_path` 字段

#### Scenario: 不修改运行时
- **WHEN** 使用逐算子预览功能
- **THEN** SHALL NOT 修改 Cleaner 运行时或逻辑算子实现

