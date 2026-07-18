## 1. 失败优先的治理契约

- [x] 1.1 更新 tooling 与测试分层契约测试，先断言根 Makefile 不存在且当前权威文档、主规范和测试不提供 Make 开发入口
- [x] 1.2 为 AGENTS.md 的 PR 前策略增加契约测试，固定九项独立必跑任务、遇错即停、`check` 不可替代完整清单及条件测试规则

## 2. 删除兼容入口

- [x] 2.1 删除根目录 `Makefile`，移除只为验证 Make 转发层存在的测试逻辑
- [x] 2.2 更新当前 OpenSpec 主规范，删除 Makefile 要求和场景，统一为 `tools.ci` 命令
- [x] 2.3 搜索非归档源码、测试、工作流和权威文档，清除剩余 Make 开发入口且不改写归档历史

## 3. PR 前手动验证策略

- [x] 3.1 在根 AGENTS.md 增加独立的 PR 前手动验证章节，列出九项必跑任务、顺序、失败处理和成功标准
- [x] 3.2 在 AGENTS.md 明确 `test-real` 与 `test-all` 的条件触发范围，并声明日常 `check` 不替代完整 PR 前清单
- [x] 3.3 更新 README 的用户命令说明，删除 Makefile 兼容描述并指向唯一 Python CI 入口

## 4. 验证

- [x] 4.1 运行受影响的 tooling、测试分层和文档治理单元测试
- [x] 4.2 逐项运行 `format-check`、`lint`、`docs`、`test`、`coverage`、`security`、`package`、`package-validate` 和 `package-smoke`
- [x] 4.3 运行 `openspec validate --all --strict`、搜索当前 Make 入口残留并审查最终 diff 不包含两个用户自有 change
