# `operators/` 模块指南

## 职责

- 定义逻辑算子、指标规格、注册表和参数计算器。
- 提供内置质量、格式、内容与重复检测能力。
- 不负责清洗运行生命周期、结果持久化或 Dataset 导出。

## 当前能力与公共入口

从 `image_gallery.operators` 使用 `OperatorSpec`、`MetricSpec`、`OperatorRegistry`、`create_default_registry`、`create_default_metric_specs` 和 `relative_to_absolute`。参数计算器属于内部扩展契约，不应随意扩大顶层导出。

## 核心契约与边界

- 用户侧算子按能力命名，底层库保持实现细节。
- OperatorSpec 只表达逻辑评估；ParameterComputer 负责生成可复用参数和 relation artifact。
- 新算子必须声明所需参数、输出列、默认配置和预览策略。
- 语义算子依赖缺失应在运行前检查阶段给出明确错误。

## 开发与验证

- 单元测试：`tests/unit/operators/`
- 当前行为：`openspec/specs/cleaning-operators/spec.md` 及各专项算子 spec
- 修改注册、选择或配置语义时同步检查 `cleaning/`。
