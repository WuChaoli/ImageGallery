## Context

仓库已通过 Windows 手动验证和真实 GitHub PR 验证证明 `tools.ci` 可跨平台承担全部开发与 CI 任务，Makefile 仅剩薄转发层。当前 AGENTS.md 虽列出命令，但没有定义 PR 前必须逐项运行的顺序和条件检查，`check` 也不覆盖安全、覆盖率和包验证。

## Goals / Non-Goals

**Goals:**

- 删除 Makefile 及当前有效的 Make 兼容契约，只保留 Python CI 入口。
- 用文档化的拆分命令清单定义 PR 创建或更新前的手动验证策略。
- 让失败能在具体阶段暴露，并用治理测试阻止入口回退。

**Non-Goals:**

- 不新增 `pre-pr` 聚合任务、Git hook 或新的第三方依赖。
- 不修改 `tools.ci check` 的日常快速检查语义。
- 不修改归档 OpenSpec 历史。

## Decisions

### PR 前验证保持拆分

AGENTS.md SHALL 按 `format-check`、`lint`、`docs`、`test`、`coverage`、`security`、`package`、`package-validate`、`package-smoke` 的顺序列出必跑命令。开发者逐条执行，任一失败立即停止，修复后从失败项继续，避免聚合任务延迟错误定位。

备选方案是新增 `pre-pr` 聚合任务或 Git hook；前者弱化阶段可见性，后者增加安装和本地工作流负担，因此均不采用。

### 条件测试按风险触发

涉及 MinIO、sample_1000 或真实数据时额外运行 `test-real`；涉及 slow、并发、缓存、状态恢复或资源生命周期时额外运行 `test-all`。日常 `check` 仍可快速反馈，但不得替代完整 PR 前清单。

### 删除而非隐藏兼容层

删除根 Makefile，并更新当前 AGENTS、README、测试和主规范中的 Make 引用。归档 change 作为历史证据保持不变。治理测试 SHALL 断言根 Makefile 不存在，并扫描当前权威文档与规范，防止重新引入 Make 入口。

## Risks / Trade-offs

- [外部脚本仍调用 Make] → 这是已确认的 breaking migration；README 与 AGENTS 明确给出 Python CI 替代入口。
- [手动清单可能漏跑] → AGENTS 将其设为明确的 PR 前硬要求，GitHub required checks 继续作为服务器端兜底。
- [逐项执行较繁琐] → 接受该成本以换取更早、更明确的失败定位；不引入聚合入口。

## Migration Plan

1. 先用失败测试固定 Makefile 必须不存在、权威内容不得引用 Make 入口。
2. 删除 Makefile 并更新当前规范、AGENTS 和 README。
3. 逐项运行新的 PR 前必跑清单与条件相关测试。

回滚时可从 Git 历史恢复 Makefile和兼容契约，但不得在没有重新确认需求的情况下保留双入口。

## Open Questions

无。
