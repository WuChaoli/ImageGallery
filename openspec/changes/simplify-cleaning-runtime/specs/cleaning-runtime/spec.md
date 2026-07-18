## ADDED Requirements

### Requirement: 计划运行生命周期一致性
系统 SHALL 对新建和恢复的计划运行使用一致的参数阶段、运行快照与失败收尾语义，同时保留两种入口各自的初始化和恢复行为。

#### Scenario: 新运行完成参数阶段
- **WHEN** 新计划运行完成参数计算
- **THEN** 系统写出最新参数表、artifact/relation 引用和 running 状态快照，再继续 evaluation/merge

#### Scenario: 恢复运行复用已完成参数节点
- **WHEN** 恢复未完成的计划运行且 SQLite 已记录 completed 参数节点
- **THEN** 系统复用已完成节点并只调度剩余参数节点，同时合并既有与新增 artifact/relation 引用

#### Scenario: 新运行失败收尾
- **WHEN** 新计划运行在已创建运行目录后发生失败
- **THEN** 系统保存最新表和 failed 状态快照、上报 run_failed，并把 SQLite run 状态更新为 failed

#### Scenario: 恢复运行失败收尾
- **WHEN** 恢复的计划运行再次发生失败
- **THEN** 系统保留原始 started_at，保存最新表和 failed 状态快照、上报 run_failed，并把 SQLite run 状态更新为 failed

#### Scenario: 公开契约保持不变
- **WHEN** 调用方通过既有 `run_graph` 或 `resume_graph` 入口执行清洗
- **THEN** 方法签名、返回值、异常和持久化格式与重构前一致
