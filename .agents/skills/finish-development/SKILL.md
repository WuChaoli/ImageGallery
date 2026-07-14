---
name: finish-development
description: 一键完成 ImageGallery 开发收尾。用于用户明确表示开发完成、要求归档 OpenSpec、同步 AGENTS/README、创建 Git 提交或完成开发分支时；依次调用 openspec-archive-change（内部强制 sync-docs）、验证变更、使用中文提交信息提交，再调用 finishing-a-development-branch。不要在测试失败、文档存在 blocker 或变更范围不明确时提交。
---

# 一键完成开发

将本 skill 作为仓库共享的一键入口，通过 `$finish-development` 显式调用。

## 工作流

1. 确认当前目录是仓库，读取适用的 `AGENTS.md`，运行 `git status --short --branch`。
2. 确定唯一的 OpenSpec change。用户未指定且无法唯一推断时，列出活动 change 并要求选择；禁止猜测。
3. 读取 change 的 artifact 状态与 `tasks.md`，要求所有 artifacts 和 tasks 完成。存在未完成项时停止并报告，不通过 archive 的宽松确认路径绕过。
4. 运行仓库规定的完整 lint 和 test。任何命令失败时停止，不归档、不提交、不进入分支收尾。
5. 调用 `openspec-archive-change` 归档选定 change。该 skill 必须先同步 main specs，再调用 `sync-docs`；出现文档 blocker 时停止。
6. 重新运行受文档或归档影响的最小验证，并执行：
   - `git diff --check`
   - `git status --short`
   - `git diff --stat`
7. 审查全部待提交文件。只纳入当前完成 change 及其必要文档；发现无法可靠归属的既有变更时停止并请求用户确认，禁止使用 `git add -A` 粗暴收集。
8. 精确暂存文件，读取 `git diff --cached --stat` 和 `git diff --cached`，确认 staged diff 非空且范围正确。
9. 创建中文提交。提交信息必须使用 `<动作>：<中文总结>`，动作从 `开发`、`修复`、`优化`、`测试`、`文档`、`维护` 中选择；除代码实体外，不使用英文描述。例如：`开发：完成 YAML 清洗配方并同步产品文档`。
10. 提交后运行 `git status --short --branch` 和 `git log -1 --oneline`，确认提交成功。
11. 调用 `finishing-a-development-branch`。遵循它的环境检测和集成选项；合并、推送、创建 PR 或丢弃仍需其规定的用户选择与安全确认。

## 不变量

- 不在测试失败时提交。
- 不在 OpenSpec 或文档尚未收敛时归档。
- 不修改、暂存或提交与目标 change 无关的用户变更。
- 不使用英文 Conventional Commit 作为最终提交标题。
- 不自动推送、合并或删除分支；这些动作由 `finishing-a-development-branch` 管理。

## 完成摘要

报告归档位置、同步的 specs、更新或判定无需更新的文档、验证命令、提交哈希和中文提交标题，然后进入分支收尾选项。
