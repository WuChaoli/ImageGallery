## Context

当前项目使用 `mypy --strict` 做类型检查（71 个源文件全量通过），使用 `ruff` 做代码风格检查（select = E, F, I, UP, B）。两者均已全量通过，但存在以下不足：

1. **mypy 不支持原生 severity 分级**：无法实现"Any 类型使用仅提示不阻断"的渐进式收紧策略，只能全或无。
2. **缺少统一入口**：无 Makefile，每次需手动拼长命令；AGENTS.md 中的命令使用 Unix 路径 (`.venv/bin/python`)，与 Windows 开发环境不一致。
3. **docstring 规范未强制执行**：AGENTS.md 明确了 docstring 规范，但无自动化检查，全靠人工 review。
4. **无 pre-commit 门禁**：类型检查和 lint 可被绕过，不构成编译期强制。

## Goals / Non-Goals

**Goals:**
- 用 pyright 替代 mypy，获得原生 warning/error severity 分级能力
- pyright strict 模式下，Any 相关规则为 warning（提示不阻断），缺类型标注为 error（阻断）
- ruff 新增 D 规则组，强制公开函数/类/方法的 docstring 存在性与格式
- 提供 `make lint` 统一入口，一条命令跑完 ruff + pyright
- 所有公开函数/类/方法（不以 `_` 开头）必须有 docstring，包括简单 getter

**Non-Goals:**
- 不引入运行时类型强制（beartype/typeguard），本阶段只做静态检查
- 不做架构依赖约束（import-linter），留待后续
- 不引入 pyright + mypy 双检查器组合，避免意见分歧的维护成本
- 不做 CI/CD pipeline 配置（只提供 `make lint` 入口和 pre-commit 可选配置）

## Decisions

### 决策 1：pyright 替代 mypy

**选择**：用 pyright 替代 mypy，而非双工具共存。

**理由**：
- pyright 原生支持 warning/error severity 分级，mypy 不支持
- pyright 是 Pylance（VS Code Python 语言服务）的底层引擎，IDE 集成更优
- pyright 通常比 mypy 更快
- 两个类型检查器共存会导致意见分歧，维护成本高
- pyright 的 Any 来源分类更精细（explicit Any vs unknown/implicit Any）

**替代方案**：
- 保留 mypy + `|| true` hack 模拟 warning：粗糙，不够结构化
- mypy + 自定义 wrapper 脚本按 error code 分类：多一个维护负担
- 最终选择 pyright，因为原生 severity 正是项目所需

**pyright 配置策略**：

| 规则 | Severity | 说明 |
|------|----------|------|
| `typeCheckingMode` | strict | 基线 |
| `reportMissingParameterType` | error | 缺类型标注必须阻断 |
| `reportMissingTypeArgument` | warning | 泛型缺类型参数提示 |
| `reportAny` | warning | 显式 Any 提示不阻断 |
| `reportUnknownVariableType` | warning | 隐式 unknown 提示不阻断 |
| `reportUnknownArgumentType` | warning | 参数 unknown 提示不阻断 |
| `reportUnknownMemberType` | warning | 成员 unknown 提示不阻断 |
| `reportPrivateImportUsage` | none | 第三方库私有导入不检查 |

### 决策 2：ruff 新增 D 规则组，从严策略

**选择**：方案 1 从严——所有不以 `_` 开头的公开函数/类/方法必须有 docstring。

**理由**：
- Python 没有语言级 public/private 关键字，ruff 靠命名约定判断（不以 `_` 开头 = public）
- 一行 docstring 成本极低，但保证 100% 覆盖率
- 与 Rust（`pub fn` 必须有文档注释）、TS（public 方法应该有 JSDoc）的理念一致
- 零豁免、零 noqa 散落、零维护负担

**D 规则选择**：

| 规则 | 说明 | 启用 |
|------|------|------|
| D101 | public class 必须有 docstring | ✓ |
| D102 | public method 必须有 docstring | ✓ |
| D103 | public function 必须有 docstring | ✓ |
| D205 | summary 与描述间空一行 | ✓ |
| D300 | 必须用三引号 | ✓ |
| D400 | 首行以句号结尾 | ✓ |
| D104 | __init__.py docstring | ✗ (太吵) |
| D105 | magic method docstring | ✗ (太多) |
| D107 | __init__ docstring | ✗ |
| D401 | imperative mood | ✗ (中文 docstring 不适用) |
| D403 | 首词大写 | ✗ (中文 docstring 不适用) |

**per-file-ignores**：`tests/**` 豁免所有 D 规则（测试代码不强制 docstring）。

### 决策 3：pyright 配置放在 pyproject.toml

**选择**：将 pyright 配置放在 `pyproject.toml` 的 `[tool.pyright]` 节，而非独立的 `pyrightconfig.json`。

**理由**：
- 项目已有 `pyproject.toml` 集中管理 ruff、pytest 等工具配置
- 减少根目录文件数量，配置集中可维护
- pyright 支持 `pyproject.toml` 配置（`[tool.pyright]` 节）

### 决策 4：Makefile 作为统一入口

**选择**：创建 Makefile，定义 `lint` target。

**理由**：
- `make` 是跨平台的事实标准（Windows 需安装 make 或使用 `just`）
- 一条命令跑完 ruff + pyright，降低使用门槛
- 可扩展（未来加 import-linter、beartype 等）

**Windows 兼容性考量**：
- Makefile 中使用 `.venv/Scripts/python.exe`（Windows 路径）而非 `.venv/bin/python`
- 或使用 `python -m pyright` / `python -m ruff` 不依赖具体路径
- 优先使用 `python -m <tool>` 形式，跨平台兼容

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| pyright 与 mypy 类型推断差异导致现有代码报错 | 实施前先运行 pyright 扫描，评估差异量，逐项修复 |
| `pip install pyright` 首次下载 Node 二进制较慢 | 文档说明首次安装预期，不影响后续使用 |
| D 规则可能发现大量缺 docstring 的函数 | 实施前先扫描，评估数量，批量补齐一行 docstring |
| Windows 上 `make` 不可用 | AGENTS.md 说明安装方式 (`choco install make` 或用 `just`)；Makefile 使用 `python -m` 跨平台 |
| pyright strict 可能比 mypy strict 更严格，出现新 error | 配置中可调整个别规则 severity，先 warning 再逐步收紧 |
