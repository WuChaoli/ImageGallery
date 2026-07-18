## Context

仓库当前包含旧平台 `storage` / `dataset` / `cleaning` 与新平台 `storage_manager` / `model_manager` / `dataset_manager` 两套独立公开 API。默认测试基线为 572 passed、1 skipped，全仓源码行覆盖率为 89.75%；现有 coverage 门槛为 89%，diff coverage 为 80%。主要维护成本来自职责聚集和重复编排，而不是明显死代码：`dataset_manager/manager.py` 约 1560 行，`cleaning/runtime.py` 约 1195 行，`operators/builtin.py` 约 919 行。

本 change 是全项目重构计划的基础 PR。它只建立可执行护栏和阶段路线图，不提前修改任何业务实现。后续每个阶段使用独立 OpenSpec change、分支和 PR，并保持前一阶段已经建立的公开契约。

## Goals / Non-Goals

**Goals:**

- 将默认快速测试的全仓源码行覆盖率底线提升到 90.00%。
- 自动冻结包级公开导出和可检查的公开调用签名。
- 用现有及新增测试守护异常、返回语义、新旧平台隔离和 Cleaning 惰性导入语义。
- 定义按依赖和风险递增的全项目重构顺序。
- 允许并发开发不修改相同领域文件的独立 PR。

**Non-Goals:**

- 不改变任何产品功能、公开 API、默认值、返回值、异常或持久化格式。
- 不在本 change 中重构业务模块。
- 不启用 branch coverage，也不提高现有 80% diff coverage 门槛。
- 不通过完整模块排除、无依据的 `pragma: no cover` 或降低测试选择范围提高覆盖率。
- 不把私有内部路径纳入稳定 API；测试、示例和 Notebook 可随内部拆分同步更新。

## Decisions

### 1. 以可执行契约而不是文档声明守护公开接口

新增集中式公开 API 契约测试，固定所有带 `__all__` 的包及其导出名称，并对可检查的函数、类和方法记录规范化签名。规范化过程按参数名称、参数类型、注解、默认值和返回注解生成结构化表示，避免依赖 `inspect` 的展示排版。Cleaning 的惰性导出需要逐项验证对象 identity，未知名称仍必须抛出 `AttributeError`。新旧 `Dataset` 和 Storage API 的隔离继续由领域语义测试证明。

选择该方案是因为单纯依赖 `__all__` 搜索无法发现签名漂移，完整序列化运行时返回值又会把动态环境细节错误地固化。集中契约测试只冻结用户选择的公开边界，领域行为仍由现有 OpenSpec 场景测试负责。

### 2. 将 90% 定义为原始源码行覆盖率门槛

`tools.ci coverage` 使用 `--cov-fail-under=90`，coverage report precision 固定为两位小数，确保 89.99% 失败、90.00% 通过。默认快速测试中的 passed / failed / error 必须保持零失败；skip 和被既有 marker 分层排除的测试不计为失败。覆盖率提升优先来自真实契约和边界测试，尤其是当前未被集中访问的 Cleaning 惰性公开入口。

没有选择“允许 10% 测试失败”，因为这与公开语义不变冲突；也没有启用 branch coverage，因为它会把本轮质量护栏扩大成不同性质的测试治理项目。

### 3. 全项目采用阶段化、独立 PR 的风险阶梯

后续 change 按以下顺序推进：

1. `establish-refactor-guardrails`：公开契约与 90% coverage。
2. Cleaning Runtime：运行、恢复、状态持久化与失败收尾去重。
3. Cleaning Result 与配置：预览、导出、结果读取和配置选择拆分。
4. Operators：内置定义、指标规格、Computer 校验与注册逻辑拆分。
5. 旧数据链路：`storage`、`dataset`、`importers`、`schemas`、`annotations`、`visualization`、`reports`。
6. 新平台基础设施：`storage_manager` 与 `model_manager`。
7. DatasetManager 生命周期：Repo、Dataset 与 facade 委托。
8. DatasetManager 历史协议：commit、clone、rollback 与 recovery。
9. DatasetManager 扩展能力：Tag、VectorField 与 embedding。
10. 全仓收敛：残留、命名、依赖方向和文档验收。

Cleaning 的两个阶段以及 DatasetManager 的三个阶段必须顺序执行，因为它们修改相同核心文件。Cleaning、Operators 和不依赖同一文件的新旧数据模块可在护栏 PR 之上并发开发。新平台基础设施完成后才能开始 DatasetManager 拆分。

### 4. 并发 PR 使用共享基线和隔离工作树

每个 PR 使用独立 worktree、分支和 OpenSpec change。首批业务重构分支从护栏分支创建，并在护栏 PR 合并后更新到 `master`。工作树复用根仓库 `.venv`，验证时禁止在 worktree 内创建独立虚拟环境；并发测试使用当前 worktree 的 `src` 和测试路径，避免 editable install 指向串扰。

没有选择单分支大爆炸重构，因为它无法隔离回归、难以审查，也不满足用户要求的并发 PR。

### 5. 每个阶段以职责和重复下降为完成条件

阶段 proposal 必须列出目标文件、重复流程或职责纠缠、公开 facade 和附加验证入口。允许增加少量私有文件，不以总代码行数或文件数机械下降为目标。只有出现真实重复且依赖方向一致时才提取共享抽象。

## Risks / Trade-offs

- [集中式签名快照可能因 Python 表示差异产生噪声] → 只存结构化规范化后的公开签名摘要，以 Python 3.10 生成基线，并由 compatibility suite 验证最新稳定 Python。
- [覆盖率提升可能诱导低价值测试] → 新增测试必须对应公开导入、异常或边界语义，禁止仅执行行而不断言结果。
- [并发 PR 基线漂移] → 以护栏分支作为首批共同基线；基础 PR 合并后逐个更新并重新运行完整门禁。
- [DatasetManager 拆分破坏跨存储一致性] → 在基础设施稳定后再分三阶段处理，commit/recovery 协议单独 PR，并强制运行 `dataset-backend`。
- [文件拆分增加导航成本] → 每个新私有模块只承担一个明确职责，并同步模块 `AGENTS.md` 与 README 导航。

## Migration Plan

1. 合并护栏 PR，固定 90% coverage 和公开 API 契约。
2. 从最新 `master` 或尚未合并的护栏分支创建独立阶段 worktree。
3. 每阶段先补 characterization test，再做内部拆分。
4. 逐项运行 PR 前门禁；涉及真实数据、生命周期或 Dataset Backend 时运行额外入口。
5. 合并后同步主规格并归档对应 change，再更新后继分支基线。
6. 若某阶段出现语义回归，关闭或回退该独立 PR，不影响已合并阶段。

## Open Questions

无。用户已授权由 Codex 决定剩余策略并完成全部阶段。
