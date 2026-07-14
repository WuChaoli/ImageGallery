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

创建 git worktree 时，继续复用原仓库的 `.venv` 作为开发与验证环境，不要在 worktree 内重新创建独立虚拟环境。

## 编码风格与命名约定

使用 Python 3.10、`src/` 布局、4 空格缩进，并保持 Google 风格的可读性。公开包名和代码命名使用英文与 snake_case。算子命名采用能力优先形式，例如 `quality.blur_check` 或 `duplicate.near_duplicate_check`；OpenCV、fastdup、CleanVision 等后端选择保持为内部实现细节。

除非相关开发计划明确要求，不要添加服务端 API、Web UI、分布式调度器或宽泛抽象。第一版代码应保持 local-first，以 Python package/API 为核心，并方便 Notebook 验证。

## 注释与 Docstring 规范

代码注释优先使用中文；公开 API、核心领域类、抽象接口、算子入口、IO 边界函数、状态变更函数、复杂私有 helper 必须编写 Python docstring。

Docstring 使用 Google Python 风格：第一行说明函数或类职责；必要时补充契约、输入前置条件、输出语义和副作用；按需使用 `Args`、`Returns`、`Raises`、`Examples` 等标准段落。参数名、类型名、字段名保持英文，解释文字使用中文。简单 getter、明显的一行转换函数、测试内部局部 helper 可不写 docstring。

函数内部中文注释只写在关键节点：数据校验与失败条件、Storage/Parquet/SQLite/图片读取等 IO 边界、批处理循环、缓存、去重、分组、merge policy 等非显然逻辑、`image_uri` 和 `source_uri` 等架构契约字段语义，以及为兼容第三方库行为而做的特殊处理。

禁止添加低价值注释：不复述代码本身，不解释显而易见的语法，不写与当前实现不一致的愿景式说明，不为未来可能发生的需求预留注释。

## 测试指南

新增行为优先采用测试先行。单元测试应按包领域组织，例如 `tests/unit/storage/test_uri.py`。集成测试只在所需底层模块已经存在后覆盖端到端流程。每个模块都应包含小而确定的测试，用于验证错误处理和产物契约。

测试和 Notebook 验证应优先复用 `notebooks/_helpers/` 中已有的路径、存储、数据集和清洗配置入口，避免在测试里重复编写项目根目录定位、MinIO 初始化、默认数据集加载或算子配置样板代码。测试功能行为需要使用真实数据集时，统一复用 `notebooks/_helpers/datasets.py` 提供的默认数据集加载入口，例如 `load_default_minio_sample_1000_dataset()` 或 `load_default_minio_sample_1000_frame()`；不要在测试或 Notebook 验证中临时自造一套功能测试数据集。

## 提交与 Pull Request 指南

当前 checkout 不是 Git 仓库，因此没有可用的本地提交历史。初始化 Git 后，使用简洁的 Conventional Commit 风格提交信息，例如 `chore: add python package metadata` 或 `feat: implement filesystem storage`。

Pull Request 应说明变更范围，列出已运行的验证命令，链接相关开发计划或架构文档，并明确非目标。只有 Notebook、报告或可视化变更需要附截图。

## 架构说明

保持 V1 边界清晰：Parquet 存数据集，SQLite 存运行状态，Storage 存图片。导入后 `image_uri` 是图片主引用；`source_uri` 用于追溯。clean、dropped 和 full 数据集必须通过 merge policy 基于逻辑算子结果生成。

## docs/ 文档状态索引

以下文档为历史参考，行为规范以 `openspec/specs/` 为准：

| 文档 | 状态 | 说明 |
|------|------|------|
| `docs/prds/图片数据集处理框架-PRD.md` | 参考 | 产品需求，已提取至 openspec specs |
| `docs/architecture/总体架构.md` | 参考 | 核心决策和数据流仍有参考价值 |
| `docs/architecture/modules/清洗平台与算子库.md` | 已 superseded | V1 原始设计，已被 V2→V3 迭代替代 |
| `docs/architecture/modules/清洗平台接口.md` | 已 superseded | V1 接口设计 |
| `docs/architecture/modules/清洗平台接口-v2.md` | 已 superseded | V2 接口设计 |
| `docs/architecture/modules/清洗平台接口-v2-文件类函数设计.md` | 已 superseded | V2 文件设计 |
| `docs/architecture/modules/清洗平台与算子库-v3.md` | 参考 | V3 设计基础，最新设计在 superpowers/ |
| `docs/architecture/modules/存储系统.md` | 参考 | 存储设计仍有参考价值 |
| `docs/architecture/modules/图片导入与元数据.md` | 参考 | 导入设计仍有参考价值 |
| `docs/architecture/modules/数据集管理与可视化.md` | 参考 | 数据集设计仍有参考价值 |
| `docs/architecture/modules/错误处理与恢复.md` | 参考 | 状态存储和恢复设计仍有参考价值 |
| `docs/architecture/modules/性能与扩展.md` | 参考 | 性能设计仍有参考价值 |
| `docs/development/` | 历史 | 分阶段开发计划，作为历史记录保留 |
| `docs/superpowers/` | 已迁移 | 最新设计已迁移至 openspec changes |

## 重构说明

当前处于开发阶段，任何开发方向的改变都是有可能的，不要保留历史兼容性，快速向未来转向，确保接口和实现干净
