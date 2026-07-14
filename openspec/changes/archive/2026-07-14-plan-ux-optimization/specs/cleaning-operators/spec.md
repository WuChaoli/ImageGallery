## MODIFIED Requirements

### Requirement: 算子短名命名（PLANNED）
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
- **WHEN** 使用 "quality.blur_check" 等旧长名格式
- **THEN** 抛出 ValueError 提示使用短名

#### Scenario: 短名算子注册表
- **WHEN** 调用 `create_default_registry().list_operators()`
- **THEN** 返回按字母排序的 17 个短名列表

### Requirement: 算子用户规则元数据（PLANNED）
系统 SHALL 为每个 OperatorSpec 附加用户规则元数据，描述该算子面向用户的动作规则结构。

#### Scenario: 规则元数据
- **WHEN** 检查某个 OperatorSpec 的用户规则元数据
- **THEN** 包含 drop 和 review 两个动作的默认阈值和描述

#### Scenario: Preview Policy 短名映射
- **WHEN** 检查内置算子的 PreviewPolicy 字典键
- **THEN** 使用短名作为键
