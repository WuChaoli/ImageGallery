---
name: sync-docs
description: 根据已完成的代码变更或 OpenSpec change 收敛仓库文档。用于归档 OpenSpec 前、公共 API 或模块边界变化后，以及用户要求同步文档时；更新根或模块 AGENTS.md 与面向人的 README，并允许在有证据时判定无需更新。不要用于维护 docs/CODEMAPS.md 或已废弃的 docs/superpowers。
---

# 同步仓库文档

让文档反映已经实现并验证的事实，不把未来设计复制成当前能力。

## 输入

优先接受 OpenSpec change 名称。未指定时，从当前对话和 `openspec list --json` 推断；若存在多个合理候选，要求用户选择。没有 OpenSpec change 时，以 staged diff 为主；没有 staged diff 时读取 working-tree diff。

开始前完整读取 [documentation-policy.md](references/documentation-policy.md)。创建或重写模块 `AGENTS.md` 时再读取 [module-agents-template.md](references/module-agents-template.md)。

## 工作流

1. 运行 `openspec status --change "<name>" --json`，读取 proposal、design、delta specs 和 tasks 中实际存在的文件。
2. 读取 `git diff --cached`；若为空，再读取 `git diff` 和相关未跟踪文件。只用 OpenSpec 判断目标，只用代码与测试判断当前实现。
3. 建立受影响能力、源码模块、公共导出、测试和用户用法的映射。
4. 按文档影响矩阵分别判断：
   - 根 `AGENTS.md`：仅全仓库治理、命令、架构边界或模块索引变化时更新。
   - 模块 `AGENTS.md`：职责、非职责、推荐入口、关键契约、依赖边界或验证方式变化时更新。
   - 根或模块 `README.md`：安装、配置、公共 API、用户工作流或用户可见行为变化时更新。
5. 只修改受影响段落。不要复制完整函数签名、OpenSpec Scenario、测试矩阵或动态文件清单。
6. 搜索已删除符号、旧用法和失效路径；确认新增链接与命令存在。
7. 输出结构化收敛结果。存在 blocker 时停止后续归档。

## 验证

- 重新读取所有修改的文档。
- 运行 `git diff --check`。
- 对文档中引用的本地路径逐一验证存在性。
- 若 README 含可执行示例，运行最小导入或对应测试验证示例仍成立。
- 确认同一事实没有在 OpenSpec、AGENTS 和 README 中逐字重复维护。

## 输出契约

```yaml
documentation_sync:
  root_agents: updated | unchanged
  module_agents:
    - path: <path>
      status: created | updated | unchanged
  readmes:
    - path: <path>
      status: created | updated | unchanged
  blockers: []
  warnings: []
```

`unchanged` 必须说明理由。以下情况是 blocker：用户可见 API 已改变但 README 仍描述旧用法；模块职责或公共入口已改变但模块 `AGENTS.md` 仍是旧状态；文档引用已删除符号或失效路径。
