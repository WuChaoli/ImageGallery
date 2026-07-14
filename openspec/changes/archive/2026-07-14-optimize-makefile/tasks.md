## 1. 基础架构改造

- [x] 1.1 删除 OS 检测 + wildcard venv 路径逻辑，所有 Python 命令改用 `uv run` 调用
- [x] 1.2 新增 `.PHONY` 声明所有 target（`lint test check format lint_diff lint_package lint_tests help`）

## 2. lint 体系扩展

- [x] 2.1 引入 `PYTHON_FILES` 变量，`lint` recipe 通过该变量控制扫描范围
- [x] 2.2 新增 `lint_package` target（仅 `src/`）、`lint_tests` target（仅 `tests/`）
- [x] 2.3 新增 `lint_diff` target：使用 `git diff --name-only --diff-filter=d master` 获取变更文件并仅检查这些文件
- [x] 2.4 验证 `lint` / `lint_package` / `lint_tests` / `lint_diff` 四种模式均能正确执行

## 3. 测试增强

- [x] 3.1 `make test` 添加 `-n auto`（pytest-xdist 并行）和 `--disable-socket --allow-unix-socket`（网络隔离）
- [x] 3.2 引入 `TEST_FILE` 和 `PYTEST_EXTRA` 变量，支持 `make test TEST_FILE=tests/unit/foo.py` 灵活运行

## 4. 新增 format 与 help target

- [x] 4.1 新增 `format` target：`uv run ruff check --fix src tests` + `uv run ruff format src tests`
- [x] 4.2 新增 `help` target：输出所有可用命令及用途说明

## 5. 验证

- [x] 5.1 运行 `make help` 确认所有 target 正确列出
- [x] 5.2 运行 `make lint` 全量通过
- [x] 5.3 运行 `make format` 后再次 `make lint` 无新增违规
- [x] 5.4 运行 `make test` 测试套件通过
- [x] 5.5 运行 `make lint_package` 仅扫描 src/，`make lint_tests` 仅扫描 tests/
