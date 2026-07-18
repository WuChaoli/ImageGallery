## Context

`CleaningRuntime._run_planned_graph` 与 `_resume_planned_graph` 都负责把已配置算子编译为计划、构造运行上下文、执行参数阶段、写表和 `state.json`、进入 evaluation/merge，并在任意阶段失败时写出 failed 快照、事件和 SQLite 状态。两条路径的输入初始化不同：新运行创建空表和新 SQLite store，恢复运行读取已有表、状态及已完成节点；除此之外生命周期几乎一致。

约束是公开 API、异常、返回值、事件顺序和 Parquet/JSON/SQLite 持久化语义不变，且本阶段不处理 `CleanerResult`。

## Goals / Non-Goals

**Goals:**

- 用 characterization tests 固定新运行、恢复运行、成功落盘和失败收尾的既有行为。
- 将计划准备、参数阶段、运行快照和失败收尾收敛为共享私有流程。
- 让 `_run_planned_graph` 与 `_resume_planned_graph` 只保留各自不同的初始化职责，降低认知复杂度。

**Non-Goals:**

- 不改变任何公开导出、方法签名、返回类型或异常类型。
- 不改变运行目录结构、状态 schema、事件名称/顺序、节点恢复判定或重试语义。
- 不修改 `CleanerResult`、evaluation/merge 算法、算子协议或存储后端。

## Decisions

### 1. 先用磁盘状态 characterization tests 锁定边界

测试通过真实临时运行目录读取 `state.json`、SQLite run record 和表文件，并观察进度事件；只在算子计算边界使用最小可控测试实现。这样测试验证外部可观察语义，而不是断言私有 helper 的调用次数。

替代方案是仅依赖现有端到端测试，但它们没有集中覆盖新运行与恢复运行在参数阶段失败后的相同收尾契约，也无法明确保护本次去重边界。

### 2. 用私有运行会话对象承载共享数据

引入模块私有 dataclass，集中保存 `run_id`、数据集指纹、解析后的算子、编译计划、路径、上下文、当前表、artifact/relation 路径、已完成算子状态和开始时间。新运行与恢复运行分别构造会话，随后交给同一参数阶段和生命周期执行函数。每个 evaluator 成功后立即把最新 tables 与 `OperatorRunState` 回写会话，使后续 evaluator 或 merge 失败时的 failed 快照保留已完成进度。

替代方案是给共享 helper 传递十余个独立参数；这会减少重复行数，却继续保留高参数复杂度和容易错配的状态。

### 3. 只抽取真正一致的生命周期

共享函数统一负责参数节点事件、调度、表写入、running 快照、调用 `_complete_planned_run`，以及异常后的 failed 快照、事件、SQLite 状态和 `RuntimeRunResult`。新建 store/记录 graph/manifests 与加载既有状态/已完成节点仍留在各入口。

替代方案是把 run/resume 合并成一个带大量布尔分支的函数；这会把重复转化为条件复杂度，反而降低可读性。

## Risks / Trade-offs

- [共享可变会话可能使数据流不清晰] → dataclass 保持模块私有，只有参数阶段和成功 evaluator 更新表、算子状态与 artifact/relation 映射，并由 characterization tests 检查落盘结果。
- [evaluation 中途失败可能回退到参数阶段旧快照] → 每个 evaluator 成功后同步更新会话 tables 与 operator states，并用两算子部分成功测试锁定失败落盘内容。
- [失败发生在运行目录创建前时，新运行与恢复运行的落盘条件不同] → 保留新运行现有的 `run_dir.exists()` 守卫，并将该差异作为共享失败函数的显式输入。
- [重构可能改变时间戳或事件顺序] → 不缓存额外时间点，沿用现有 `started_at` 选择和事件发出位置，并在测试中断言关键顺序。

## Migration Plan

无需数据迁移。先提交 characterization tests，再替换私有编排实现；任一验证失败时可直接回滚本次提交，既有运行目录格式不受影响。

## Open Questions

无。公开与持久化边界已由用户确认。
