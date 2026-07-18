## 1. 公开接口契约基线

- [x] 1.1 新增 `tests/unit/test_public_api_contract.py`，显式固定所有带 `__all__` 的包及其当前公开导出名称，并验证导出对象可以解析。
- [x] 1.2 在公开接口契约测试中固定可检查的公开函数与类构造签名，失败信息必须指出发生漂移的完整符号。
- [x] 1.3 新增 Cleaning 惰性导入契约用例，逐项访问全部公开导出并验证未知名称仍抛出 `AttributeError`。
- [x] 1.4 复核并运行 Dataset、Storage 新旧平台隔离测试，确认集中契约未把私有内部路径误纳入稳定接口。

## 2. 覆盖率门槛提升

- [x] 2.1 先将 `tests/unit/tooling/test_ci_command.py` 的期望门槛改为 90，并运行目标测试确认现有 `tools.ci` 实现失败。
- [x] 2.2 将 `tools/ci.py` 的全仓 coverage 参数修改为 `--cov-fail-under=90`，保持 80% diff coverage 与默认测试选择参数不变。
- [x] 2.3 运行公开接口契约与 tooling 测试，确认签名、惰性导入和 CI 参数测试全部通过。
- [x] 2.4 运行 `uv run python -m tools.ci coverage`，确认所有已执行测试零失败且原始源码行覆盖率达到或高于 90.00%。

## 3. 规范、文档与全项目路线图

- [x] 3.1 验证 `test-quality-gates` delta spec 完整表达 90% 全仓覆盖率、80% diff coverage 与公开接口契约回归门禁。
- [x] 3.2 复核 `design.md` 的阶段依赖、并发 PR 拓扑、额外测试入口和回滚边界，不保留占位符或未决策略。
- [x] 3.3 使用 `sync-docs` 检查根与模块文档，仅在公开开发门槛或导航确有变化时进行最小同步。

## 4. PR 前验证

- [x] 4.1 依次运行 `format-check`、`lint`、`docs`、`test` 和 `coverage`，任一失败时停止并从失败项修复。
- [x] 4.2 依次运行 `security`、`package`、`package-validate` 和 `package-smoke`，确认所有必跑任务退出码为 0。
- [x] 4.3 审查最终 diff，确认没有业务实现、公开 API、默认值、返回语义或无关用户修改混入本 PR。
