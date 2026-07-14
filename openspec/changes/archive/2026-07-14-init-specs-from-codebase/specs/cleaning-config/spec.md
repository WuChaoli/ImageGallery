## ADDED Requirements

### Requirement: CleanerConfig TOML 配置
系统 SHALL 提供 `CleanerConfig`，从 TOML 文件或映射对象加载清洗配置，包含算子选择、算子配置覆盖和节点策略。

#### Scenario: 从 TOML 文件加载
- **WHEN** 调用 `CleanerConfig.from_toml(path)` 读取有效的 TOML 配置文件
- **THEN** 返回包含 operators、operator_configs、node_policy 和 operator_policies 的 CleanerConfig

#### Scenario: 从映射对象加载
- **WHEN** 调用 `CleanerConfig.from_mapping(payload)` 传入字典
- **THEN** 解析 cleaner、operator、node_policy 和 operator_policies 各段

#### Scenario: operators 选择字段
- **WHEN** TOML 中 cleaners.operators 为字符串 "ALL"
- **THEN** 解析为 ["ALL"] 选择器

#### Scenario: operator 配置段
- **WHEN** TOML 中包含 [[operator]] 段且每段有 name 字段
- **THEN** 解析为 {name: config} 的 operator_configs 字典

### Requirement: select_operators 算子选择器
系统 SHALL 提供 `select_operators()` 函数，按选择器（名称、分类或 "ALL"）展开为已配置算子列表。

#### Scenario: 展开 ALL 选择器
- **WHEN** 传入选择器 "ALL"
- **THEN** 返回注册表中所有算子的 ConfiguredOperatorSpec 列表

#### Scenario: 按分类展开
- **WHEN** 传入选择器 "quality"（分类名）
- **THEN** 返回该分类下所有算子的 ConfiguredOperatorSpec 列表

#### Scenario: 按名称展开
- **WHEN** 传入选择器 "quality.blur_check"（含点号的算子名）
- **THEN** 验证该算子存在于注册表并返回单个 ConfiguredOperatorSpec

#### Scenario: 未知选择器
- **WHEN** 传入无法识别的选择器字符串
- **THEN** 抛出 ValueError 提示可用的分类列表

#### Scenario: 内联配置
- **WHEN** 选择器附带内联配置字典
- **THEN** 内联配置与默认配置合并后生成 ConfiguredOperatorSpec

#### Scenario: 配置覆盖
- **WHEN** 传入 overrides 参数覆盖某个算子的配置
- **THEN** 该算子使用覆盖后的配置

### Requirement: TOML 模板导出
系统 SHALL 提供 `build_cleaner_toml_template()` 函数，为给定算子选择器生成不含密钥的 cleaner TOML 模板。

#### Scenario: 生成模板
- **WHEN** 调用 `build_cleaner_toml_template(["quality", "duplicate"])`
- **THEN** 返回包含 [cleaner]、[node_policy] 和各 [[operator]] 段的 TOML 字符串

#### Scenario: 模板包含默认配置
- **WHEN** 生成的模板中包含某个算子
- **THEN** 该算子的 [[operator]] 段包含其默认配置键值对（None 值跳过）

#### Scenario: BasicCleaner 模板导出方法
- **WHEN** 调用 `BasicCleaner.export_config_template(path, operators)`
- **THEN** 将 TOML 模板写入指定路径并返回 Path
