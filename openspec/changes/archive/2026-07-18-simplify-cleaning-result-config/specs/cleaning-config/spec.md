## ADDED Requirements

### Requirement: Cleaning 配置入口语义稳定

系统 SHALL 在内部解析职责拆分后保持 TOML `CleanerConfig` 和 YAML `CleanerRecipe` 的选择、编译、校验及错误语义不变。

#### Scenario: TOML 入口保持独立

- **WHEN** 调用 `CleanerConfig.from_toml()` 或 `from_mapping()`
- **THEN** 继续解析 `[select]`、`[operators]` 和 `[runtime]`，且不新增 YAML 配置入口

#### Scenario: 选择段互斥

- **WHEN** 配置同时包含 `[select]` 与 `[operators]`
- **THEN** 继续抛出 `ValueError` 并报告两段互斥

#### Scenario: 嵌套策略校验

- **WHEN** 全局或算子级 runtime policy 包含无效类型
- **THEN** 继续抛出相同类型的异常并保留对应字段的错误上下文

#### Scenario: TOML 模板往返

- **WHEN** 生成 cleaner TOML 模板后再次通过 `CleanerConfig.from_toml()` 加载
- **THEN** 算子选择、默认配置和全局 runtime policy 与重构前一致

#### Scenario: YAML Recipe 编译

- **WHEN** 从 YAML 加载 version、run 和 operators 并调用 `compile_selectors()`
- **THEN** 继续校验版本与短名，并生成相同 selector 列表和错误语义
