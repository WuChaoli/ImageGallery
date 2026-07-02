# 仓库指南

## 项目结构与模块组织

本仓库当前以文档先行为主。产品需求位于 `docs/prds/`，架构入口位于 `docs/architecture/`，模块设计位于 `docs/architecture/modules/`，分阶段开发计划位于 `docs/development/`。

计划中的 Python 包结构是 `src/image_gallery/`，按领域拆分为 `storage`、`dataset`、`schemas`、`state`、`importers`、`cleaning`、`operators`、`visualization`、`reports` 和 `utils`。测试应放在 `tests/unit/` 与 `tests/integration/`；示例和 Notebook 验证入口应放在 `examples/` 与 `notebooks/`。

## 构建、测试与开发命令

阶段 0 创建包骨架后，使用以下命令：

```bash
uv venv .venv --python 3.10 --seed
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

`uv venv .venv --python 3.10 --seed` 创建带 pip 的项目本地虚拟环境。`pip install -e ".[dev]"` 安装本地包和开发工具。`pytest` 运行测试套件。`ruff` 检查 lint 和 import 顺序。`mypy` 对包执行严格类型检查。运行和测试统一使用 `.venv/bin/python`。

## 编码风格与命名约定

使用 Python 3.10、`src/` 布局、4 空格缩进，并保持 Google 风格的可读性。公开包名和代码命名使用英文与 snake_case。算子命名采用能力优先形式，例如 `quality.blur_check` 或 `duplicate.near_duplicate_check`；OpenCV、fastdup、CleanVision 等后端选择保持为内部实现细节。

除非相关开发计划明确要求，不要添加服务端 API、Web UI、分布式调度器或宽泛抽象。第一版代码应保持 local-first，以 Python package/API 为核心，并方便 Notebook 验证。

## 测试指南

新增行为优先采用测试先行。单元测试应按包领域组织，例如 `tests/unit/storage/test_uri.py`。集成测试只在所需底层模块已经存在后覆盖端到端流程。每个模块都应包含小而确定的测试，用于验证错误处理和产物契约。

## 提交与 Pull Request 指南

当前 checkout 不是 Git 仓库，因此没有可用的本地提交历史。初始化 Git 后，使用简洁的 Conventional Commit 风格提交信息，例如 `chore: add python package metadata` 或 `feat: implement filesystem storage`。

Pull Request 应说明变更范围，列出已运行的验证命令，链接相关开发计划或架构文档，并明确非目标。只有 Notebook、报告或可视化变更需要附截图。

## 架构说明

保持 V1 边界清晰：Parquet 存数据集，SQLite 存运行状态，Storage 存图片。导入后 `image_uri` 是图片主引用；`source_uri` 用于追溯。clean、dropped 和 full 数据集必须通过 merge policy 基于逻辑算子结果生成。
