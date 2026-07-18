## Why

Makefile 兼容层已经完成过渡使命，继续保留会让开发者面对两套入口，并要求测试和文档长期维护重复契约。同时，当前仓库只列出检查命令，没有明确 PR 创建或更新前逐项执行、遇错即停的手动验证策略。

## What Changes

- **BREAKING**：删除根目录 `Makefile`，移除所有当前有效文档、测试和主规范中的 Make 兼容入口。
- 将 `uv run python -m tools.ci <task>` 设为唯一的本地与 CI 命令入口。
- 在根 `AGENTS.md` 中新增 PR 提交前手动验证策略，要求格式、lint、文档、默认测试、覆盖率、安全和包验证逐项执行，任一失败立即停止并修复。
- 明确 `test-real` 与 `test-all` 的条件触发范围，不新增聚合 `pre-pr` 任务或 Git hook。
- 增加治理测试，防止当前文档、规范或测试重新引入 Makefile 入口。
- 保留归档 OpenSpec 中的历史记录，不回写历史 change。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `developer-command-harness`：删除 Makefile 兼容层要求，增加唯一 Python CI 入口和拆分式 PR 前验证要求。
- `lint-pipeline`：移除 Makefile 场景和旧命令引用，统一使用 Python CI lint 入口。
- `test-dataset-strategy`：将默认测试入口从 Makefile 更新为 Python CI，并明确条件测试策略。
- `development-guidelines`：删除同时提供 Make 与底层命令的要求，统一为跨平台 Python CI 入口。

## Impact

- 删除根目录 `Makefile`。
- 更新 `AGENTS.md`、`README.md`、相关治理测试和 OpenSpec 主规范。
- `tools.ci` 任务实现保持拆分，不新增聚合入口。
- 仍依赖 GNU Make 的本地调用将失效，开发者必须迁移到 `uv run python -m tools.ci <task>`。
