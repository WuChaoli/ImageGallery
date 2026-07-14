# cleaning-operators Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
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

### Requirement: ConfiguredOperatorSpec 已配置算子
系统 SHALL 提供 `ConfiguredOperatorSpec`，绑定 OperatorSpec 与合并后配置，并生成稳定的配置哈希。

#### Scenario: 从 spec 构建配置
- **WHEN** 调用 `ConfiguredOperatorSpec.from_spec(spec, config, source)`
- **THEN** 合并 spec.default_config 和传入 config，生成 operator_config_hash

#### Scenario: 配置哈希稳定性
- **WHEN** 两个 ConfiguredOperatorSpec 的合并配置完全相同
- **THEN** 它们的 operator_config_hash 相同

### Requirement: OperatorRegistry 算子注册表
系统 SHALL 提供 `OperatorRegistry`，支持注册算子规格和参数计算单元，并按名称或分类查询。

#### Scenario: 注册算子
- **WHEN** 调用 `registry.register_operator(spec)`
- **THEN** 后续可通过 `registry.get_operator(name)` 查询到该 spec

#### Scenario: 注册参数计算单元
- **WHEN** 调用 `registry.register_parameter_computer(computer)`
- **THEN** 后续可通过 `registry.get_parameter_computer(name)` 查询

#### Scenario: 查询不存在的算子
- **WHEN** 调用 `registry.get_operator("nonexistent")`
- **THEN** 抛出 KeyError

#### Scenario: 列出所有算子
- **WHEN** 调用 `registry.list_operator_specs()`
- **THEN** 返回所有已注册的 OperatorSpec 列表

#### Scenario: 列出所有分类
- **WHEN** 调用 `registry.list_categories()`
- **THEN** 返回所有算子分类名称列表

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

### Requirement: ParameterComputer 参数计算单元
系统 SHALL 提供 `ParameterComputer` 抽象基类，作为参数节点的计算后端，支持按 ExecutionMode 声明执行模式和运行前依赖校验。

#### Scenario: 参数计算单元注册
- **WHEN** 调用 `create_default_registry()` 创建默认注册表
- **THEN** 注册了 ImageMetadataComputer、TableDerivedComputer、ImageQualityComputer、ImageQualityDetailComputer、ImageBorderComputer、ImageHashComputer、DuplicateGroupComputer、SemanticEmbeddingComputer 等参数计算单元

#### Scenario: 语义嵌入提供者
- **WHEN** 创建注册表时传入 semantic_providers
- **THEN** SemanticEmbeddingComputer 使用指定的提供者进行语义嵌入计算

#### Scenario: before_run_check 默认空操作
- **WHEN** ParameterComputer 子类未覆盖 before_run_check 方法
- **THEN** 调用 before_run_check() SHALL 为空操作，不抛出异常

#### Scenario: before_run_check 签名
- **WHEN** 检查 ParameterComputer.before_run_check 方法签名
- **THEN** SHALL 接受可选 config 参数并返回 None，未传 config 时仍可作为默认空操作调用

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

### Requirement: 算子用户规则元数据（PLANNED）
系统 SHALL 为每个 OperatorSpec 附加用户规则元数据，描述该算子面向用户的动作规则结构。

#### Scenario: 规则元数据
- **WHEN** 检查某个 OperatorSpec 的用户规则元数据
- **THEN** 包含 drop 和 review 两个动作的默认阈值和描述

#### Scenario: Preview Policy 短名映射
- **WHEN** 检查内置算子的 PreviewPolicy 字典键
- **THEN** 使用短名作为键
