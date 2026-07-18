## MODIFIED Requirements

### Requirement: 默认测试与真实数据验收分层

系统 SHALL 将依赖 `sample_1000` 或 MinIO 的测试同时标记为 `slow` 和 `real_dataset`，Python CI 默认 `test` 任务 SHALL 排除 `slow` 测试。PR 涉及 MinIO、sample_1000 或真实数据时 MUST 额外运行 `test-real`；涉及 slow、并发、缓存、状态恢复或资源生命周期时 MUST 额外运行 `test-all`。

#### Scenario: 运行默认测试
- **WHEN** 执行 `uv run python -m tools.ci test`
- **THEN** pytest SHALL 不收集 slow 测试，且清洗集成测试 SHALL 使用本地 sample_10

#### Scenario: 运行真实数据验收
- **WHEN** 变更涉及真实数据并执行 `uv run python -m tools.ci test-real`
- **THEN** pytest SHALL 仅运行 `real_dataset` 测试，并允许在 MinIO 或 sample_1000 不可用时明确跳过

#### Scenario: 运行完整测试
- **WHEN** 高风险运行时变更执行 `uv run python -m tools.ci test-all`
- **THEN** pytest SHALL 同时收集默认测试、slow 测试和真实数据测试
