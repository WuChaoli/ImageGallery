## MODIFIED Requirements

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
