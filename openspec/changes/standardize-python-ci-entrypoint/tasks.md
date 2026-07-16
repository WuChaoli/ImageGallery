## 1. Python CI 入口契约

- [x] 1.1 为任务列表、固定 argv、未知任务和帮助输出编写失败优先的单元测试
- [x] 1.2 为组合任务顺序、首错停止、退出码传播和输出透传编写单元测试
- [x] 1.3 实现轻量 `tools.ci` 模块，使入口在 Windows 与 Linux 上不依赖 shell 或 GNU Make

## 2. 格式化与质量任务

- [x] 2.1 为 `format`、`format-check`、`lint` 和 `check` 的命令范围与只读/修改语义补充测试
- [x] 2.2 实现 Ruff 自动修复、Ruff formatter、Ruff check、Pyright 和默认快速测试任务组合
- [x] 2.3 将 Ruff 格式与 lint 范围统一覆盖 `src`、`tests` 和仓库级 Python CI 工具，并修复首次格式检查发现的机械格式差异

## 3. 现有任务迁移

- [x] 3.1 将默认测试、真实数据测试、完整测试、安全检查、包构建、安装 smoke test 和 SBOM 命令迁移到 Python CI 任务
- [x] 3.2 将 Makefile 目标改为 Python CI 的薄兼容转发，并增加测试防止重复维护底层参数
- [ ] 3.3 手动验证 Makefile 兼容目标与对应 Python CI 任务具有一致的成功和失败结果

## 4. GitHub CI 迁移

- [x] 4.1 更新 CI、安全、定时安全和发布 workflows，使其直接调用 Python CI 入口且不依赖 Make
- [x] 4.2 保持现有 required job 名称、最小权限、Action SHA 固定和凭据隔离，并更新 workflow 契约测试
- [x] 4.3 在 lint required check 中先执行 `format-check` 再执行 `lint`，验证未格式化代码会阻止 PR 且 CI 不修改 checkout

## 5. 文档与本地验证

- [x] 5.1 同步根与相关模块 AGENTS.md、README 和命令帮助，明确 Python 入口为权威入口、Makefile 为临时兼容层
- [ ] 5.2 在 Windows 手动运行 `format-check`、`lint`、默认测试、安全检查、包构建与 smoke test，并记录真实结果
- [x] 5.3 运行 Ruff、Pyright、默认 pytest、CI 工具单元测试和 `openspec validate --strict`，确认工作树没有非预期格式修改

## 6. GitHub 验证与兼容期结论

- [ ] 6.1 通过 Pull Request 验证 `lint`、`test`、`package`、`secrets`、`dependencies` 和 `workflows` required checks 均使用新入口并成功
- [ ] 6.2 记录 Windows 手动验证与 GitHub CI 结果，确认本轮继续保留 Makefile
- [x] 6.3 仅在后续独立变更中评估删除 Makefile，不在本 change 中执行删除
