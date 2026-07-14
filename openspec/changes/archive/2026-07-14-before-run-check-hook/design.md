## Context

`ParameterComputer` 基类当前只有 `compute()` 抽象方法，所有依赖和资源校验在 `compute()` 内部执行。语义去重相关的 Computer（`SemanticEmbeddingComputer`、`SemanticDuplicateGroupComputer`）在 `compute()` 中通过 `load_semantic_provider()` 触发 `onnxruntime`/`huggingface-hub`/`faiss-cpu` 的导入和模型加载，失败时抛出 `SemanticDependencyError`。

当前 `CleaningRuntime.run_graph()` 按状态图拓扑序逐个执行参数节点，如果 semantic 节点排在最后，用户需要等前面所有节点跑完才能得到依赖缺失错误。

`build_dry_run_result()` 用于 compile/dry-run 诊断，但目前不执行任何依赖校验。

## Goals / Non-Goals

**Goals:**
- `ParameterComputer.before_run_check()` 在 compile 和 run 阶段提前校验依赖和资源
- 语义算子 Computer 覆盖钩子，检查可选依赖可导入和模型路径可访问
- dry-run 阶段也能触发校验，实现秒级反馈

**Non-Goals:**
- 不改变 `compute()` 内部的现有校验逻辑
- 不引入新的异常类型（复用 `SemanticDependencyError`）
- 不实现通用插件发现或自动安装机制

## Decisions

### 决策 1：钩子放在基类而非接口

在 `ParameterComputer` 基类添加 `before_run_check()` 方法（默认空操作），而非定义独立 Protocol。

**理由**: 所有 Computer 已继承 `ParameterComputer`，加默认空方法零迁移成本。独立 Protocol 需要类型检查和注册逻辑改造，收益不大。

**替代方案**: `PreFlightCheckable` Protocol — 需要额外类型判断，且只有 semantic Computer 需要实现，过度设计。

### 决策 2：调用时机 — run_graph 入口 + dry-run

在 `CleaningRuntime.run_graph()` 的参数节点调度循环前，收集所有用到的 Computer 并逐个调用 `before_run_check()`。在 `build_dry_run_result()` 中同样调用。

**理由**: 在参数计算开始前统一校验，确保所有 Computer 就绪后才开始执行。dry-run 作为诊断入口也需要同样的校验。

**替代方案**: 每个节点执行前单独调用 — 不够"早"，如果 semantic 节点排在后面还是会晚报错。

### 决策 3：SemanticEmbeddingComputer 检查内容

仅检查 `onnxruntime` 和 `huggingface_hub` 可导入（try import），不尝试加载模型或创建 session。模型路径检查仅在用户显式指定 `model_path` 时校验文件存在性。

**理由**: 模型加载可能耗时长（下载），不适合放在 pre-flight 检查中。import 检查能覆盖 90% 的常见错误（未安装可选依赖）。

## Risks / Trade-offs

- **[风险] 未来其他 Computer 也需要 before_run_check** → 基类默认空操作，新增覆盖不影响现有 Computer
- **[风险] import 检查通过但运行时仍失败** → 可接受，`compute()` 中的现有校验仍作为兜底
- **[取舍] 不检查模型下载可用性** → HuggingFace 网络问题不在 pre-flight 范围内，运行时错误信息已足够清晰
