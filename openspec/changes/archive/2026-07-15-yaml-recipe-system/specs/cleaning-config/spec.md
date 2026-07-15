## MODIFIED Requirements

### Requirement: ActionRange 区间规则解析
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

### Requirement: MetricSpec 阈值元数据
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

### Requirement: YAML Recipe 系统
系统 SHALL 提供 `CleanerRecipe` 类，从 YAML 文件加载用户友好的清洗配方，编译为内部 operator selector 列表。

#### Scenario: 从 YAML 加载
- **WHEN** 调用 `CleanerRecipe.from_yaml(path)` 读取有效 YAML 文件
- **THEN** 返回 CleanerRecipe，包含 version、run_defaults 和 operators 列表

#### Scenario: YAML 结构
- **WHEN** YAML 包含 version、run 和 operators 三段
- **THEN** version 默认为 1 且必须等于 1；run 包含 output_dir、cache_root；operators 是非空列表

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

### Requirement: 双级动作评估
系统 SHALL 支持基于区间规则的双级动作评估（drop 和 review），按优先级 drop > review > keep 顺序评估。

#### Scenario: 相对指标的区间评估
- **WHEN** blur 算子配置 `rules: {drop: "[0, 0.3]", review: "(0.3, 0.6]"}` 且 blur_score 归一化后为 0.2
- **THEN** 该图片的 blur_action 为 "drop"

#### Scenario: 绝对指标的阈值评估
- **WHEN** dimension 算子配置 `drop: {min_width: 256}` 且图片宽度为 200
- **THEN** 该图片的 dimension_action 为 "drop"
