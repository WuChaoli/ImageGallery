# 仓库指南

## 项目结构与模块组织

本仓库以 OpenSpec 规范驱动开发。`openspec/specs/` 表达当前已接受的产品行为，`openspec/changes/` 表达未来设计与实现状态。`docs/superpowers/` 已废弃，仅作历史参考；原始设计文档已备份至根目录 `docs-backup.tar.gz`。

Python 包结构为 `src/image_gallery/`，按领域拆分如下：

```text
src/image_gallery/
├── storage/          # 图片存储抽象层（本地文件系统 + MinIO）
├── dataset/          # 数据集管理（Parquet 读写、Schema 契约、标签校验）
├── schemas/          # 数据契约与类型定义
├── state/            # 运行时状态持久化（SQLite）
├── importers/        # 多源导入（本地目录、URL 列表、MinIO）
├── cleaning/         # 清洗运行时（算子调度、计划编译、断点恢复、HTML 预览）
├── operators/        # 内置算子库（重复检测、质量检查、安全过滤等）
├── visualization/    # 图片预览与结果可视化
├── reports/          # 清洗报告生成
└── utils/            # 通用工具函数
```

**存储职责边界**：Parquet 存数据集，SQLite 存运行状态，Storage 存图片。测试应放在 `tests/unit/` 与 `tests/integration/`；示例和 Notebook 验证入口应放在 `examples/` 与 `notebooks/`。

## 文档体系与权威性

| 问题 | 权威来源 |
|------|----------|
| 产品当前承诺什么行为 | `openspec/specs/` |
| 产品正在怎样变化 | `openspec/changes/` |
| 当前实现实际上是什么 | 代码、类型和测试 |
| AI 应如何修改仓库或模块 | 根目录与模块目录的 `AGENTS.md` |
| 人如何安装和使用 | 根目录或模块目录的 `README.md` |
| 旧设计为何如此 | `docs/superpowers/`、`docs-backup.tar.gz` 等历史归档 |

根 `AGENTS.md` 只维护全仓库治理、全局边界和模块导航；模块 `AGENTS.md` 维护局部职责、推荐入口、关键契约、依赖边界和验证方法。不要在 AGENTS 中复制完整 API 签名、OpenSpec Scenario、测试矩阵或动态文件清单。

开发完成后使用 `$finish-development` 一键执行验证、OpenSpec 归档、`$sync-docs` 文档收敛、中文 Git 提交和分支收尾。直接归档 OpenSpec 时，`openspec-archive-change` 也必须先调用 `sync-docs`。本仓库不使用通用 `codemap` 创建或维护 `docs/CODEMAPS.md`。

## 开发生命周期

仓库开发必须遵循以下闭环：

1. **需求澄清**：先使用 `superpowers:brainstorming` 明确目标、范围、非目标、候选方案和成功标准，并取得用户对设计的确认。需要调查复杂代码现状、分析已有 change 或验证关键假设时，按需使用 `openspec-explore`；它不是每次开发的必经步骤。
2. **OpenSpec 规划**：设计确认后使用 `openspec-propose` 创建 change；需求或设计变化时使用 `openspec-update-change`。`openspec/changes/<change>/` 是本轮开发目标、设计和任务状态的唯一来源。
3. **Superpowers 开发**：以已确认的 OpenSpec change 为输入，使用 `openspec-apply-change` 推进 tasks，并按任务性质使用 Superpowers 的 TDD、系统调试、计划执行和完成前验证等开发技能。实现结果必须通过代码和测试证明，不能把 `docs/superpowers/` 的历史文档当作当前设计。
4. **结束开发**：所有 artifacts、tasks、lint 和 test 完成后，显式调用 `$finish-development`。该入口负责同步 main specs、运行 `$sync-docs`、归档 change、创建中文 Git 提交，并进入 `finishing-a-development-branch` 的分支集成流程。
5. **进入下一轮**：未完成或验证失败时返回当前 change 继续开发；归档和分支收尾完成后，新的需求重新从需求澄清开始。

未取得 brainstorming 设计确认时不得调用 `openspec-propose`；未形成已确认的 OpenSpec change 时不得开始实现。不得跳过 OpenSpec 直接把临时想法实现为产品行为；不得在验证失败或文档尚未收敛时归档、提交或进入分支集成。

## 构建、测试与开发命令

使用 `uv` 管理环境和依赖。以下命令提供了 `make` 快捷方式和底层等价命令：

```bash
# 安装开发环境
uv venv .venv --python 3.10 --seed
uv sync --extra dev

# 一键 lint（ruff 代码风格 + docstring + pyright 类型检查）
make lint
# 等价手动命令：
uv run ruff check src tests
uv run pyright src/image_gallery

# 运行测试
make test
# 等价手动命令：
uv run pytest -n auto --disable-socket --allow-unix-socket -m "not slow" tests/

# 运行依赖 sample_1000 和 MinIO 的真实数据验收
make test_real
# 等价手动命令：
uv run pytest -n 0 --disable-socket -o addopts= -m "real_dataset" tests/

# 运行包含 slow 的完整测试
make test_all
# 等价手动命令：
uv run pytest -n auto --disable-socket --allow-unix-socket -o addopts= tests/

# lint + test 全量检查
make check

# 运行单个测试文件
uv run pytest tests/unit/cleaning/test_specific.py
```

**注意**：Windows 用户如未安装 GNU Make，可直接使用等价手工命令。`pyright` 类型检查中 warning 不阻断，error 阻断。

创建 git worktree 时，继续复用原仓库的 `.venv` 作为开发与验证环境，不要在 worktree 内重新创建独立虚拟环境。

## 编码风格与命名约定

使用 Python 3.10、`src/` 布局、4 空格缩进，并保持 Google 风格的可读性。公开包名和代码命名使用英文与 snake_case。内置算子命名采用能力短名形式，例如 `blur`、`dimension` 或 `semantic_duplicate`；OpenCV、fastdup、CleanVision 等后端选择保持为内部实现细节。

除非相关开发计划明确要求，不要添加服务端 API、Web UI、分布式调度器或宽泛抽象。第一版代码应保持 local-first，以 Python package/API 为核心，并方便 Notebook 验证。

## 注释与 Docstring 规范

代码注释优先使用中文；所有不以 `_` 开头的公开函数、类、方法必须编写 Python docstring（由 ruff D101/D102/D103 规则强制检查，测试文件豁免）。

Docstring 使用 Google Python 风格：第一行说明函数或类职责；必要时补充契约、输入前置条件、输出语义和副作用；按需使用 `Args`、`Returns`、`Raises`、`Examples` 等标准段落。参数名、类型名、字段名保持英文，解释文字使用中文。所有公开函数（包括简单 getter）必须有 docstring，一行 `"""返回 xxx。"""` 即可。测试文件（`tests/**`）豁免 docstring 检查。

函数内部中文注释只写在关键节点：数据校验与失败条件、Storage/Parquet/SQLite/图片读取等 IO 边界、批处理循环、缓存、去重、分组、merge policy 等非显然逻辑、`image_uri` 和 `source_uri` 等架构契约字段语义，以及为兼容第三方库行为而做的特殊处理。

禁止添加低价值注释：不复述代码本身，不解释显而易见的语法，不写与当前实现不一致的愿景式说明，不为未来可能发生的需求预留注释。

## 类型检查与 cast 规范

项目使用 pyright strict 模式进行编译期类型检查。Any 相关规则（reportAny、reportUnknownVariableType 等）设为 warning 不阻断；缺失类型标注、参数类型不匹配等规则设为 error 阻断。

**pandas 类型窄化规则**：pyright 对 pandas DataFrame/Series 的类型推断较宽（返回联合类型），需要在关键位置用 `typing.cast` 显式窄化：

- `pd.to_numeric(...)` 返回联合类型，必须 `cast(pd.Series, pd.to_numeric(...))`
- `frame[column]` 列索引返回联合类型，传递给期望 `pd.Series` 的函数时需 `cast(pd.Series, frame[column])`
- `frame[frame[column] == value]` 布尔过滤返回联合类型，重新赋值给 `frame` 时需 `cast(pd.DataFrame, ...)`
- `frame[[col1, col2]]` 多列索引返回联合类型，需 `cast(pd.DataFrame, frame[[col1, col2]])`
- `pd.isna(value)` 返回 `bool | NDArray | NDFrame`，在 `if` 条件中需 `cast(bool, pd.isna(value))`
- `series.value_counts().items()` 返回 `Hashable` 键，需 `str(hash_value)` 或 `cast` 窄化
- `series.get(key, default)` 返回 `Unknown | None`，传给 `int()` 时需 `cast("int | float | None", ...)`
- `frame.to_dict(orient="records")` 返回类型不精确，需 `cast(list[dict[str, object]], ...)`
- 第三方库构造函数签名不匹配时，用 `# pyright: ignore[reportCallIssue]` 行级豁免

禁止用 `# type: ignore` 粗暴跳过类型检查。优先用 `cast` 精确窄化；只有第三方库自身的类型定义问题才用 `# pyright: ignore[rule]` 行级豁免。

## 测试指南

新增行为优先采用测试先行。单元测试应按包领域组织，例如 `tests/unit/storage/test_uri.py`。集成测试只在所需底层模块已经存在后覆盖端到端流程。

默认功能测试统一使用 `tests/fixtures/sample_10/` 中固定的 10 张本地图片，并通过 `tests/helpers/sample_dataset.py` 装配为当前 checkout 可读取的 Dataset，不得连接 MinIO。完全重复、近似重复、空白和异常尺寸等精确边界行为继续使用测试内专用确定性输入，不假定 sample_10 包含特定类别。

`sample_1000` 仅用于 Notebook 人工验证和带 `slow`、`real_dataset` marker 的真实数据验收。需要该数据集时统一复用 `notebooks/_helpers/datasets.py` 的 `load_default_minio_sample_1000_dataset()` 或 `load_default_minio_sample_1000_frame()`；默认 `make test` 排除这些测试，使用 `make test_real` 显式运行。

### 测试覆盖检查清单

每个新功能或 bugfix 必须通过以下检查：

- [ ] **Happy path 覆盖**：正常路径有对应的单元测试
- [ ] **边界和错误条件**：异常输入、空值、边界值已测试
- [ ] **Mock 外部依赖**：单元测试不发起网络调用（文件 IO / MinIO 用 fixture 模拟）
- [ ] **确定性**：测试结果不依赖执行顺序、外部状态或随机性
- [ ] **Fail when broken**：新增逻辑被移除或破坏后，对应测试会失败

## 公共接口稳定性

**CRITICAL**：修改公开 API 前必须逐项检查以下清单。

### 公共接口变更检查清单

在修改导出的函数、类或方法前：

- [ ] 该符号是否在 `__init__.py` 中导出（`__all__` 或显式 import）
- [ ] 是否已搜索测试和示例中的现有使用模式
- [ ] 新参数是否使用 keyword-only（`*, new_param: type = default`）
- [ ] 是否属于 breaking change —— 如果是，先与开发者讨论兼容方案
- [ ] 实验性功能是否在 docstring 中添加 `!!! warning` 标注

**灵魂拷问**："这个改动会让上周还在用的人代码坏掉吗？"

## 提交与 Pull Request 指南

### 提交信息（Commit）

提交标题必须使用中文 `<动作>：<总结>` 格式：

```text
<动作>：<中文总结>
```

**动作**：`开发` | `修复` | `优化` | `测试` | `文档` | `维护`

- 总结必须使用简体中文；代码实体名、库名和协议名可保留英文。
- 标题应说明完成的结果，不写执行流水账。
- 提交前必须审查 staged diff，不得混入与当前变更无关的用户修改。

示例：

```text
开发：增加清洗任务断点恢复能力
修复：处理 Storage 连接时 bucket 不存在的问题
优化：减少清洗运行时的内存占用
测试：补充 Dataset 导出边界用例
文档：同步清洗配方使用说明
```

### 分支命名

```text
<username>/<scope>/<short-description>
```

- kebab-case，例如 `mdrxy/cleaning/resume-from-checkpoint`

### PR 描述

- 关闭 Issue 时：`Closes #123` 独占首行，后跟 `---` 分隔线
- 正文说明 **why 而非 what**（谁受益、有什么问题、怎么解决）。对可能不熟悉该区域的读者友好
- 不要引用行号（会过时），少用完整文件路径
- 类、函数、方法、参数名用反引号包裹
- 新功能或行为变更 PR 必须包含 `## Release note` 小节
- 在描述末尾声明 AI 参与度
- 除非测试覆盖不显然或有风险，省略专门的 "Test plan" 小节

## 架构说明

导入后 `image_uri` 是图片主引用；`source_uri` 用于追溯来源。clean、dropped 和 full 数据集通过 merge policy 基于逻辑算子结果生成。

## docs/ 文档状态

当前产品行为以 `openspec/specs/` 为准，活动设计和实现状态以 `openspec/changes/` 为准。原始设计文档（PRD、架构、开发计划）已备份至 `docs-backup.tar.gz`。

| 目录 | 状态 | 说明 |
|------|------|------|
| `docs/superpowers/` | 已废弃 | 仅保留历史设计记录，不得作为当前实现依据 |
| `docs/testing/` | 参考 | 测试检查清单 |
| `docs-backup.tar.gz` | 备份 | 包含原 `docs/prds/`、`docs/architecture/`、`docs/development/` 全部内容 |

## 安全与风险评估

- ❌ 禁止对用户可控输入使用 `eval()`、`exec()`、`pickle.load()`
- ❌ 禁止裸 `except:`（必须指定异常类型）
- ❌ 禁止保留已注释掉或不可达的代码
- ✅ 资源使用后必须关闭（优先用 context manager）
- ✅ 注意跨线程操作的竞态条件和资源泄漏

## 重构说明

当前处于开发阶段，任何开发方向的改变都是有可能的，不要保留历史兼容性，快速向未来转向，确保接口和实现干净。
