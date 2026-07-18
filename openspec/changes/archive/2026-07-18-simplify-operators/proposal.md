## Why

`operators/builtin.py` 同时承担默认注册表装配、17 个 OperatorSpec 定义、17 个 MetricSpec 定义、预览策略和评估器实现，文件体量与认知负担已显著高于模块内其他单一职责文件。现在需要在不改变任何公开契约的前提下拆分这些静态目录职责，为后续维护内置算子降低误改风险。

## What Changes

- 用 characterization tests 固化默认算子、指标、参数计算单元和预览策略的完整语义。
- 将内置 OperatorSpec、PreviewPolicy 与 MetricSpec 的静态定义从 `builtin.py` 拆到私有模块。
- 保留 `create_default_registry()`、`create_default_metric_specs()`、公开导出、函数签名、返回值和异常语义不变。
- 保留评估器和 Cleaning 边界，不扩展本次重构范围。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cleaning-operators`: 补充默认注册工厂在内部重构后必须保持算子规格、指标规格、参数计算单元及对象独立性的兼容性要求；既有产品行为不变。

## Impact

- 影响 `src/image_gallery/operators/` 内私有实现与对应单元测试。
- Cleaning planner/graph 仅做兼容性回归验证，不修改其实现。
- 不新增依赖，不改变顶层 `__all__`、OpenSpec 既有行为或公开 API。
