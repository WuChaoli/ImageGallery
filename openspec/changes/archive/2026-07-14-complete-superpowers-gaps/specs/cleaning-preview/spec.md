## ADDED Requirements

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
