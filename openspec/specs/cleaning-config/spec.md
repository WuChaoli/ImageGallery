# cleaning-config Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
### Requirement: CleanerConfig TOML 配置
系统 SHALL 提供 `CleanerConfig`，从 TOML 文件或映射对象加载清洗配置，使用 `[select]` + `[operators]` + `[runtime]` 三段式结构。

#### Scenario: 从 TOML 文件加载
- **WHEN** 调用 `CleanerConfig.from_toml(path)` 读取有效的 TOML 配置文件
- **THEN** 返回包含 selectors、operator_configs 和 node_policy 的 CleanerConfig

#### Scenario: 从映射对象加载
- **WHEN** 调用 `CleanerConfig.from_mapping(payload)` 传入字典
- **THEN** 解析 select、operators 和 runtime 各段

#### Scenario: select 段 — 分类选择
- **WHEN** TOML 包含 `[select]` 段且 `categories = ["quality", "duplicate"]`
- **THEN** 解析为按分类选择这些分类下的所有算子

#### Scenario: select 段 — ALL 选择
- **WHEN** TOML 包含 `[select]` 段且 `categories = ["ALL"]`
- **THEN** 选择注册表中所有算子

#### Scenario: operators 段 — 显式配置
- **WHEN** TOML 包含 `[operators]` 段且 `blur = { min_score = 100.0 }`
- **THEN** 选择 `blur` 算子并覆盖其 `min_score` 配置

#### Scenario: operators 段 — 空配置表
- **WHEN** TOML 包含 `[operators]` 段且 `exact_duplicate = {}`
- **THEN** 选择 `exact_duplicate` 算子并使用其默认配置

#### Scenario: select 和 operators 互斥
- **WHEN** TOML 同时包含 `[select]` 和 `[operators]` 段
- **THEN** 抛出 ValueError 提示两段互斥

#### Scenario: runtime 段 — 拍平参数
- **WHEN** TOML 包含 `[runtime]` 段且 `batch_size = 128`
- **THEN** 解析为全局 NodePolicy 的 `batch.size` 字段

#### Scenario: runtime 段 — 算子级覆盖
- **WHEN** TOML 包含 `[operators.blur.runtime]` 段且 `batch_size = 32`
- **THEN** 解析为 `blur` 算子的独立 NodePolicy 覆盖

### Requirement: select_operators 算子选择器
系统 SHALL 提供 `select_operators()` 函数，按选择器（短名、分类或 "ALL"）展开为已配置算子列表。

#### Scenario: 展开 ALL 选择器
- **WHEN** 传入选择器 "ALL"
- **THEN** 返回注册表中所有算子的 ConfiguredOperatorSpec 列表

#### Scenario: 按分类展开
- **WHEN** 传入选择器 "quality"（分类名）
- **THEN** 返回该分类下所有算子的 ConfiguredOperatorSpec 列表

#### Scenario: 按短名展开
- **WHEN** 传入选择器 "blur"（短名，在注册表中存在）
- **THEN** 返回单个 ConfiguredOperatorSpec

#### Scenario: 未知选择器
- **WHEN** 传入无法识别的选择器字符串
- **THEN** 抛出 ValueError 提示可用的分类和算子名列表

#### Scenario: 旧长名格式报错
- **WHEN** 传入含 `.` 的选择器（如 "quality.blur_check"）且不在注册表中
- **THEN** 抛出 ValueError，提示使用短名

#### Scenario: 内联配置
- **WHEN** 选择器附带内联配置字典
- **THEN** 内联配置与默认配置合并后生成 ConfiguredOperatorSpec

#### Scenario: 配置覆盖
- **WHEN** 传入 overrides 参数覆盖某个算子的配置
- **THEN** 该算子使用覆盖后的配置

### Requirement: TOML 模板导出
系统 SHALL 提供 `build_cleaner_toml_template()` 函数，为给定算子选择器生成新结构的 cleaner TOML 模板。

#### Scenario: 生成模板
- **WHEN** 调用 `build_cleaner_toml_template(["quality", "duplicate"])`
- **THEN** 返回包含 `[operators]` 和 `[runtime]` 段且可被 `CleanerConfig.from_toml()` 重新加载的 TOML 字符串

#### Scenario: 模板包含默认配置
- **WHEN** 生成的模板中包含某个算子
- **THEN** 该算子在 `[operators]` 段以 `{ key = value }` 内联表形式输出（None 值跳过）

#### Scenario: 空配置输出空表
- **WHEN** 某个算子使用全部默认配置
- **THEN** 输出 `operator_name = {}`

#### Scenario: BasicCleaner 模板导出方法
- **WHEN** 调用 `BasicCleaner.export_config_template(path, operators)`
- **THEN** 将 TOML 模板写入指定路径并返回 Path

### Requirement: YAML Recipe 系统（PLANNED）
系统 SHALL 提供 `CleanerRecipe` 类，从 YAML 文件加载用户友好的清洗配方，编译为内部 operator selector 列表。

#### Scenario: 从 YAML 加载
- **WHEN** 调用 `CleanerRecipe.from_yaml(path)` 读取有效 YAML 文件
- **THEN** 返回 CleanerRecipe，包含 version、run_defaults 和 operators 列表

#### Scenario: YAML 结构
- **WHEN** YAML 包含 version、run 和 operators 三段
- **THEN** version 默认为 1 且必须等于 1；run 包含 output_dir、cache_root、storage；operators 是非空列表

#### Scenario: 算子配置块
- **WHEN** operators 中某项为 `{use: blur, rules: {drop: "[0, 0.3]", review: "(0.3, 0.6]"}}`
- **THEN** 编译为 `{"blur": {"rules": {"drop": "[0, 0.3]", "review": "(0.3, 0.6]"}}}` selector

#### Scenario: 绝对阈值块
- **WHEN** operators 中某项为 `{use: dimension, drop: {min_width: 256}, review: {min_width: 512}}`
- **THEN** 编译为 `{"dimension": {"drop": {"min_width": 256}, "review": {"min_width": 512}}}` selector

#### Scenario: 布尔/分组类算子
- **WHEN** operators 中某项为 `{use: decode, action: drop}`
- **THEN** 编译为 `{"decode": {"action": "drop"}}` selector

#### Scenario: from_recipe 工厂
- **WHEN** 调用 `BasicCleaner.from_recipe(yaml_path)`
- **THEN** 解析 YAML 并构造 BasicCleaner 实例

### Requirement: ActionRange 区间规则解析（PLANNED）
系统 SHALL 提供 `ActionRange` 类，解析数学区间语法表达的动作阈值。

#### Scenario: 闭区间
- **WHEN** 解析 `"[0, 0.3]"`
- **THEN** lower=0.0, upper=0.3, lower_inclusive=True, upper_inclusive=True

#### Scenario: 左开右闭
- **WHEN** 解析 `"(0.3, 0.6]"`
- **THEN** lower=0.3, upper=0.6, lower_inclusive=False, upper_inclusive=True

#### Scenario: 包含判断
- **WHEN** ActionRange `[0, 0.3]` 调用 contains(0.3)
- **THEN** 返回 True

#### Scenario: 无效语法
- **WHEN** 解析 `"0.3,0.6"` （缺少括号）
- **THEN** 抛出 ValueError

#### Scenario: 不支持无穷
- **WHEN** 解析包含 infinity 的区间
- **THEN** 抛出 ValueError（第一版不支持）

### Requirement: MetricSpec 阈值元数据（PLANNED）
系统 SHALL 提供 `MetricSpec` 数据类，描述每个算子用户可调指标的类型、范围和方向。

#### Scenario: 绝对值指标
- **WHEN** dimension 算子的 min_width 指标
- **THEN** value_type="absolute"，用户配置值直接作为阈值

#### Scenario: 相对值指标
- **WHEN** blur 算子的 blur_score 指标
- **THEN** value_type="relative"，absolute_min=0.0, absolute_max=300.0, direction="higher_better"

#### Scenario: 相对到绝对映射
- **WHEN** 调用 `relative_to_absolute(metric, 0.5)` 且 metric 的 absolute 范围为 [0, 300]
- **THEN** 返回 150.0

#### Scenario: 超出范围
- **WHEN** 调用 `relative_to_absolute(metric, 1.1)`
- **THEN** 抛出 ValueError

#### Scenario: 分类指标
- **WHEN** decode 算子的 decode_ok 指标
- **THEN** value_type="categorical"，direction="categorical"

### Requirement: 双级动作评估（PLANNED）
系统 SHALL 支持基于区间规则的双级动作评估（drop 和 review），按优先级 drop > review > keep 顺序评估。

#### Scenario: 相对指标的区间评估
- **WHEN** blur 算子配置 `rules: {drop: "[0, 0.3]", review: "(0.3, 0.6]"}` 且 blur_score 归一化后为 0.2
- **THEN** 该图片的 blur_action 为 "drop"

#### Scenario: 绝对指标的阈值评估
- **WHEN** dimension 算子配置 `drop: {min_width: 256}` 且图片宽度为 200
- **THEN** 该图片的 dimension_action 为 "drop"
