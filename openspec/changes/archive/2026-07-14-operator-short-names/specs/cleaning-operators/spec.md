## MODIFIED Requirements

### Requirement: 内置算子目录
系统 SHALL 通过 `create_default_registry()` 提供以下内置逻辑算子，按能力域分类，使用短名作为主标识。

#### Scenario: format 类算子
- **WHEN** 检查注册表中的 format 类算子
- **THEN** 包含 `decode` 和 `animated`

#### Scenario: size 类算子
- **WHEN** 检查注册表中的 size 类算子
- **THEN** 包含 `dimension`、`aspect_ratio` 和 `megapixel`

#### Scenario: quality 类算子
- **WHEN** 检查注册表中的 quality 类算子
- **THEN** 包含 `blur`、`brightness`、`contrast`、`exposure` 和 `noise`

#### Scenario: content 类算子
- **WHEN** 检查注册表中的 content 类算子
- **THEN** 包含 `blank`、`mono_color` 和 `border_padding`

#### Scenario: metadata 类算子
- **WHEN** 检查注册表中的 metadata 类算子
- **THEN** 包含 `orientation`

#### Scenario: duplicate 类算子
- **WHEN** 检查注册表中的 duplicate 类算子
- **THEN** 包含 `exact_duplicate`、`perceptual_duplicate` 和 `semantic_duplicate`

### Requirement: 算子短名命名
系统 SHALL 将所有内置逻辑算子的主标识从 `category.operator_check` 长名格式迁移为短名格式，不保留旧长名兼容。

#### Scenario: 短名映射
- **WHEN** 检查内置算子名称
- **THEN** 17 个算子使用短名：decode, dimension, aspect_ratio, megapixel, blur, brightness, contrast, exposure, noise, blank, mono_color, border_padding, animated, orientation, exact_duplicate, perceptual_duplicate, semantic_duplicate

#### Scenario: 分类选择器保留
- **WHEN** 使用分类名选择算子（如 "quality"、"duplicate"）
- **THEN** 展开为该分类下所有短名算子的列表

#### Scenario: 分类选择不区分大小写
- **WHEN** 使用 "QUALITY" 或 "Quality" 作为选择器
- **THEN** 与 "quality" 等效

#### Scenario: 旧长名报错
- **WHEN** 使用 "quality.blur_check" 等旧长名格式（含 `.` 且不在注册表中）
- **THEN** 抛出 ValueError，提示可用的短名和分类列表

#### Scenario: 短名算子注册表
- **WHEN** 调用 `create_default_registry().list_operators()`
- **THEN** 返回 17 个短名算子

### Requirement: OperatorSpec 逻辑算子规格
系统 SHALL 提供 `OperatorSpec`，描述算子的名称、分类、所需参数、评估输出列、默认配置、action 列、reason 列和评估器函数。算子名称 SHALL 使用短名格式。

#### Scenario: 算子评估
- **WHEN** 调用 `spec.evaluate(parameter_table, config)`
- **THEN** 基于 parameter_table 和 config 生成该算子的 evaluation 列 DataFrame

#### Scenario: 缺少必需参数
- **WHEN** parameter_table 缺少 required_parameters 中的列
- **THEN** 抛出 ValueError 列出缺失的参数名

#### Scenario: 评估结果列校验
- **WHEN** 评估器返回的 DataFrame 缺少 evaluation_columns 中的列
- **THEN** 抛出 ValueError 列出缺失的列名
