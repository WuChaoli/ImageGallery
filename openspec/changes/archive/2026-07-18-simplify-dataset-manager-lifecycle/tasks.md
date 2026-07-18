## 1. 生命周期 Characterization Tests

- [x] 1.1 补充 DatasetManager factory、context manager 与外部注入资源所有权测试，固定 close 次数和异常传播。
- [x] 1.2 复核 Repo 名称冲突，并补充 Dataset 创建中断、普通 API 可见性与恢复幂等测试。
- [x] 1.3 补充 Storage Prefix 绑定、重启恢复、跨 Repo 授权与 operation intent/phase/failed 状态测试。

## 2. 私有 Operation Journal

- [x] 2.1 提取 start、intent update、phase record、finalize 和 fail 的私有 journal，保持现有事务边界与事件写入。
- [x] 2.2 让 DatasetManager recovery 和各领域操作委托 journal，不改变恢复分派、异常或幂等语义。
- [x] 2.3 运行生命周期与 backend migration 相关测试，确认没有控制面 schema 或状态转换漂移。

## 3. Repo/Dataset 控制面拆分

- [x] 3.1 提取 Repo/Dataset row mapping、可见查询和控制面登记职责，保持 namespace/table 创建编排在 DatasetManager。
- [x] 3.2 提取 Storage Prefix 绑定、授权查询和运行时定义恢复职责，保持 StorageManager 公开行为不变。
- [x] 3.3 简化 DatasetManager 门面委托并移除本次变更产生的重复 helper、导入和分支。

## 4. 规范、文档与验证

- [x] 4.1 运行 `tests/unit/dataset_manager`、默认 test、coverage、`test-all` 和 `dataset-backend`，确认全部执行测试通过且覆盖率不低于 90%。
- [x] 4.2 依次运行 `format-check`、`lint`、`docs`、`test`、`coverage`、`security`、`package`、`package-validate`、`package-smoke`。
- [x] 4.3 使用 `sync-docs` 检查 DatasetManager 模块导航，仅在职责边界确有变化时最小同步。
- [x] 4.4 审查最终 diff，确认公开契约、异常、持久化 schema 和无关用户修改均未变化。
