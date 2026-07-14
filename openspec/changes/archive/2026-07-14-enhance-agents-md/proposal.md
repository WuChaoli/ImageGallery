## Why

当前 `AGENTS.md` 的覆盖面和精确度远低于顶级开源项目（如 LangChain）的 `CLAUDE.md`。AI Agent 在开发时缺少足够的约束和检查机制，导致提交规范不统一、测试覆盖不完整、公共接口容易被无意破坏等问题。借本仓库尚处早期阶段的窗口期，将 AGENTS.md 升级为一份高质量的 AI 开发指南，让 Agent 能产出更一致、更可靠的代码。

## What Changes

1. **提交/分支/PR 规范细化**：补充 Conventional Commits 的 scope 规则、分支命名模板、PR 描述格式指南（包括关闭 issue、Release note、AI 参与申明等）。
2. **公共接口变更检查清单**：新增面向 AI 的公共 API 稳定性检查步骤，要求在修改 exported symbol 前检查 `__init__.py` 导出、现有使用模式、keyword-only 参数等。
3. **可勾选的测试 checklist**：将测试要求从文字段落改为可勾选的 checklist 格式，覆盖 happy path、边界条件、mock 外部依赖、确定性等。
4. **安全红线声明**：明确列出禁止的操作（eval/exec/pickle、bare except、资源泄漏等）。
5. **命令底层等价形式**：在 `make test` / `make lint` 基础上，补充直接可用的 `uv run --group test pytest ...` 等等价命令。
6. **架构目录职责标注**：为 `src/image_gallery/` 下各子包补充职责说明和依赖流向。

## Capabilities

### New Capabilities

- `development-guidelines`: AI Agent 开发行为规范与检查清单，涵盖提交规范、接口稳定性、测试要求、安全红线等

### Modified Capabilities

（无。本次变更不修改任何现有功能规格的行为要求。）

## Impact

- **修改文件**：`AGENTS.md`（根目录）
- **新增文件**：`openspec/specs/development-guidelines/spec.md`（AI 开发指南规格文档）
- **无代码影响**：不影响 `src/` 下任何模块、API 或依赖
