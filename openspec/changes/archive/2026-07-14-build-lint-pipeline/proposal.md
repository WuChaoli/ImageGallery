## Why

Python 是动态类型语言，类型标注不强制执行，类型错误只能运行时暴露。当前项目虽已配置 `mypy --strict` 且全量通过，但 mypy 不支持原生 warning/error 严重性分级，无法实现"Any 提示但不阻断"的渐进式收紧策略。同时项目缺少统一的 `make lint` 入口和 pre-commit 门禁，类型检查和代码风格检查分散在手动命令中，无法形成编译期强制类型安全保障。

## What Changes

- **BREAKING**: 用 pyright 替代 mypy 作为类型检查器，删除 mypy 依赖和 `[tool.mypy]` 配置
- 新增 pyright 配置（`pyrightconfig.json` 或 `pyproject.toml [tool.pyright]`），启用 strict 模式，Any 相关规则设为 warning（不阻断），缺类型标注设为 error（阻断）
- ruff 规则新增 D 规则组（D101/D102/D103/D205/D300/D400），强制公开函数/类/方法的 docstring 存在性与格式
- ruff 新增 `per-file-ignores`，豁免 `tests/**` 的 D 规则
- 新增 Makefile，提供 `make lint` 统一入口（ruff + pyright）
- **BREAKING**: 更新 AGENTS.md，删除 mypy 命令，新增 pyright 和 `make lint` 命令，更新 docstring 规范取消"简单 getter 可不写 docstring"的例外
- 新增 pre-commit hook 配置（可选）

## Capabilities

### New Capabilities

- `lint-pipeline`: 静态检查工具链与门禁体系，涵盖类型检查（pyright）、代码风格与 docstring 检查（ruff）、统一入口（make lint）和门禁策略

### Modified Capabilities

（无。本变更不修改任何现有领域 spec 的需求。）

## Impact

- **pyproject.toml**: dev 依赖删除 mypy、新增 pyright；ruff lint select 新增 D 规则；新增 per-file-ignores；新增 `[tool.pyright]` 或新建 `pyrightconfig.json`；删除 `[tool.mypy]`
- **Makefile**: 新增文件，定义 `lint` target
- **AGENTS.md**: 更新构建/测试/lint 命令段落，更新 docstring 规范段落
- **现有源码**: 需扫描补齐不合规的公开函数/类/方法 docstring
- **开发流程**: 所有开发者需改用 `make lint`，pre-commit hook 拦截不合规提交
- **CI/CD**: lint 阶段从 mypy 切换为 pyright + ruff
