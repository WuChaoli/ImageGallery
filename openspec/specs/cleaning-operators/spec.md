# cleaning-operators Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: OperatorSpec 逻辑算子规格
系统 SHALL 提供 `OperatorSpec`，描述算子的名称、分类、所需参数、评估输出列、默认配置、action 列、reason 列和评估器函数。

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
系统 SHALL 通过 `create_default_registry()` 提供以下内置逻辑算子，按能力域分类。

#### Scenario: format 类算子
- **WHEN** 检查注册表中的 format 类算子
- **THEN** 包含 `format.decode_check` 和 `format.animated_image_check`

#### Scenario: size 类算子
- **WHEN** 检查注册表中的 size 类算子
- **THEN** 包含 `size.dimension_check`、`size.aspect_ratio_check` 和 `size.megapixel_check`

#### Scenario: quality 类算子
- **WHEN** 检查注册表中的 quality 类算子
- **THEN** 包含 `quality.blur_check`、`quality.brightness_check`、`quality.contrast_check`、`quality.exposure_check` 和 `quality.noise_check`

#### Scenario: content 类算子
- **WHEN** 检查注册表中的 content 类算子
- **THEN** 包含 `content.blank_image_check`、`content.mono_color_check` 和 `content.border_padding_check`

#### Scenario: metadata 类算子
- **WHEN** 检查注册表中的 metadata 类算子
- **THEN** 包含 `metadata.orientation_check`

#### Scenario: duplicate 类算子
- **WHEN** 检查注册表中的 duplicate 类算子
- **THEN** 包含 `duplicate.exact_duplicate_check`、`duplicate.perceptual_duplicate_check` 和 `duplicate.semantic_duplicate_check`

### Requirement: ParameterComputer 参数计算单元
系统 SHALL 提供 `ParameterComputer` 抽象基类，作为参数节点的计算后端，支持按 ExecutionMode 声明执行模式。

#### Scenario: 参数计算单元注册
- **WHEN** 调用 `create_default_registry()` 创建默认注册表
- **THEN** 注册了 ImageMetadataComputer、TableDerivedComputer、ImageQualityComputer、ImageBorderComputer、ImageHashComputer、DuplicateGroupComputer、SemanticEmbeddingComputer 等参数计算单元

#### Scenario: 语义嵌入提供者
- **WHEN** 创建注册表时传入 semantic_providers
- **THEN** SemanticEmbeddingComputer 使用指定的提供者进行语义嵌入计算

