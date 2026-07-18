## Context

`CleaningRunPlanner._parameter_computer_configs`、`execution._parameter_computer_configs` 与 `graph._collect_parameter_plan` 分别实现了同一组规则：从逻辑算子要求的参数展开 ParameterComputer 依赖闭包，只投影 computer 声明的配置键，对空配置使用 `default` hash，并拒绝共享 computer 的冲突配置。三处输入对象略有差异，但核心输入都可以规整为 `(OperatorSpec, config)`。同时 `compile_state_graph` 内联构造 staged 与普通参数节点，使图编译主流程同时承担策略选择、依赖映射和节点装配。

## Goals / Non-Goals

**Goals:**

- 为 ParameterComputer 配置解析建立单一私有实现，供 planner、graph 与 dry-run 复用。
- 保持依赖闭包、配置投影、hash、冲突异常和计划/节点稳定顺序不变。
- 将参数 GraphNode 装配收敛到窄私有函数，降低 `compile_state_graph` 的分支复杂度。
- 通过 characterization 与 mutation-style 测试证明三个调用面共享相同规则。

**Non-Goals:**

- 不新增公共 API，不更改公开导出、签名或异常类型/文本。
- 不改写 scheduler、runtime、结果/config 阶段或 SQLite DDL/schema。
- 不改变 checkpoint、policy、hook、失败恢复、产物与 relation 语义。

## Decisions

1. 新增 cleaning 私有模块 `_parameter_config.py`，接收 `Iterable[tuple[OperatorSpec, Mapping[str, object]]]` 和 registry，返回按 computer name 索引的配置与 hash。相比为 planner/graph 建立新领域对象，这个边界只表达三处已有的最小公共输入，避免额外抽象。
2. 依赖闭包遍历、配置投影、hash 与冲突检测全部留在同一函数中；planner 仍独立负责 requested parameter 聚合和稳定拓扑排序，graph 仍独立负责节点依赖与策略，因此不会把不同执行职责耦合进通用框架。
3. graph 仅提取 `_build_parameter_nodes` 私有函数，原样保留 staged/普通节点分支及追加顺序。相比拆分每个 GraphNode 字段计算，该方案能缩短主编译流程但不会打散节点语义。
4. 测试先记录 planner、graph、dry-run 在深层依赖、默认/投影配置和冲突上的现有输出，再通过 monkeypatch 共享 helper 验证三个入口均委托同一解析边界；公开接口契约测试继续作为最终护栏。

## Risks / Trade-offs

- [风险] 规整输入时误用未合并配置，导致 planner hash 改变 → planner 传入现有 `merged_config`，graph/dry-run 传入现有 `configured.config`，并锁定精确 hash。
- [风险] 共享 helper 改变遍历或冲突检测顺序 → 保留参数排序、computer 名称排序及原异常文本，用 characterization tests 校验。
- [风险] graph 节点提取改变 staged 节点顺序或策略 → helper 返回原顺序的列表，并比较完整 node 序列与 `plan_hash`。

## Migration Plan

无需数据迁移。变更仅调整私有代码；若验证失败，可回退 helper 提取而不影响状态数据。

## Open Questions

无。
