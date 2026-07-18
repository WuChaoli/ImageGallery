## ADDED Requirements

### Requirement: Dataset durable operation 状态语义稳定

系统 SHALL 在 operation journal 私有化后保持 Dataset 创建和后续领域操作的 durable intent、阶段事件、完成、失败与恢复语义不变。

#### Scenario: Operation intent 可恢复

- **WHEN** 跨 Iceberg 与控制面的操作在候选状态持久化后中断
- **THEN** intent 保留恢复所需的同一组字段，`recover_operations()` 继续选择相同动作并可幂等完成

#### Scenario: 阶段事件顺序保持不变

- **WHEN** 操作依次创建候选、发布引用并完成 finalize
- **THEN** 控制面记录与重构前相同的 phase 顺序，完成状态不保留错误信息

#### Scenario: 失败状态保留 intent

- **WHEN** 操作无法恢复并被标记失败
- **THEN** durable operation 保留最后 intent 与已完成 phase 并标记为 failed，普通 Dataset API 不暴露未 finalize 的对象
