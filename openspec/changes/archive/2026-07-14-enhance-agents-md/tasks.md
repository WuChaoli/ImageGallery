## 1. 前期准备

- [x] 1.1 完整阅读当前 AGENTS.md，标记每个章节的现有内容和待补充缺口
- [x] 1.2 对照 proposal.md 的 6 项变更和 design.md 的结构方案，确认每项变更应归入的章节位置

## 2. 增强已有章节

- [x] 2.1 **构建/测试/开发命令**：为 `make test`、`make lint`、`make check` 补充 `uv run` 底层等价命令，标注所需 `--group`
- [x] 2.2 **提交与 PR 指南**：补充 scope 规则（列出所有可用 scope 值）、分支命名模板 `<username>/<scope>/<short-description>`、PR 描述格式（关闭 issue 格式、why 优先、Release note、AI 参与申明）
- [x] 2.3 **测试指南**：将测试要求从文字段落改为可勾选的 checklist 格式（happy path、边界条件、mock、确定性、fail when broken）
- [x] 2.4 **架构说明**：为 `src/image_gallery/` 下各子包补充一行职责标注和依赖流向说明

## 3. 新增章节

- [x] 3.1 **公共接口稳定性**：新增章节，包含修改 public API 前的检查清单（检查 `__init__.py` 导出、搜索现有使用模式、keyword-only 新参数、breaking change 警告）
- [x] 3.2 **安全与风险评估**：新增章节，列出禁止模式（eval/exec/pickle、bare except、资源泄漏、注释代码清理）

## 4. 审查与验证

- [x] 4.1 全文自审：AGENTS.md 语言风格是否一致（中文为主、代码示例英文）
- [x] 4.2 检查每条新增规范是否附带具体示例（正反例）
- [x] 4.3 对比 specs/development-guidelines/spec.md 确保每条 Requirement 在 AGENTS.md 中都有对应落地
