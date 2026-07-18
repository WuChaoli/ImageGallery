## Context

`operators/builtin.py` 目前约 900 行：它既装配 12 个 ParameterComputer，又构造 17 个 OperatorSpec 和 17 个 MetricSpec，还包含预览策略与全部评估器。公开工厂已被 Cleaning planner、graph、selection 和 recipe 使用，因此重构必须以完整语义 characterization 为边界，而不能顺带调整契约。

## Goals / Non-Goals

**Goals:**

- 让 `builtin.py` 只保留默认注册表装配和兼容导入，降低文件认知负担。
- 将 OperatorSpec 目录、MetricSpec 目录和 evaluator 实现拆成职责明确的私有模块。
- 精确保持算子顺序、字段、默认配置、PreviewPolicy、evaluator 绑定、指标字段、ParameterComputer 顺序以及 semantic provider 注入。
- 用稳定序列化 characterization tests 和 Cleaning 定向测试证明兼容性。

**Non-Goals:**

- 不改变 `image_gallery.operators.__all__`、公开工厂签名、返回类型或异常语义。
- 不修改 OperatorSpec、MetricSpec、OperatorRegistry 数据模型。
- 不重构 Cleaning，不改变 evaluator 算法，也不引入新的注册抽象或配置格式。
- 不归档本 change，不推送或创建 PR。

## Decisions

### 1. 保留 `builtin.py` 作为稳定门面

`create_default_registry()` 继续在原模块装配 ParameterComputer，并调用私有 catalog builder 注册 OperatorSpec。`create_default_metric_specs()` 和现有 evaluator 名称通过显式同名导入保留原模块访问路径。

备选方案是直接移动公开工厂并修改所有调用方，但这会制造无必要的导入路径变化，不符合兼容边界。

### 2. 按变化原因拆成三个私有模块

- `_builtin_evaluators.py`：仅放评估器与其数值转换/原因生成 helper。
- `_builtin_specs.py`：仅构造 OperatorSpec 并附加 PreviewPolicy。
- `_builtin_metrics.py`：仅构造 MetricSpec 字典。

这种拆分让算法、目录元数据和指标元数据可独立阅读。相比把每个算子拆成一个文件，它避免 17 个极小模块与高导航成本；相比用大型声明式字典生成所有 spec，它保留当前显式构造的类型可读性。

### 3. Characterization 使用规范化语义摘要

测试将 dataclass 字段、evaluator 名称、PreviewPolicy、MetricSpec 和 ParameterComputer 契约规范化后计算稳定摘要，同时直接比较私有 builder 与公开工厂输出。摘要在重构前采集，任何字段、顺序或绑定变化都会触发失败。

此外验证重复调用返回相互独立的可变配置/策略对象，避免把静态目录误实现成共享单例。

## Risks / Trade-offs

- [显式兼容导入可能被误删] → characterization test 校验 evaluator 仍可从 `operators.builtin` 访问，并由 lint 检查导入。
- [哈希摘要诊断信息不够直观] → 保留已有逐字段测试，并在摘要 helper 中产生可打印的规范化 payload。
- [拆分引入循环导入] → 依赖方向固定为 `builtin` → specs/metrics/evaluators，specs → evaluators；私有模块不反向导入 `builtin`。
- [对象共享造成跨调用污染] → 测试验证两次工厂调用的 spec、config 与 preview policy 身份独立。

## Migration Plan

本次是内部重构，无数据迁移和调用方迁移。若验证失败，回滚私有模块与 `builtin.py` 门面改动即可恢复原实现。

## Open Questions

无。公开兼容边界与验证门槛已由用户确认。
