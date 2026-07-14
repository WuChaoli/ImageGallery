# 仓库指南

## 项目结构与模块组织

本仓库以 openspec 规范驱动开发。行为规范位于 `openspec/specs/`，最新设计规格和实现计划位于 `docs/superpowers/`。原始设计文档已备份至根目录 `docs-backup.tar.gz`。

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

## 构建、测试与开发命令

使用 `uv` 管理环境和依赖。以下命令提供了 `make` 快捷方式和底层等价命令：

```bash
# 安装开发环境
uv venv .venv --python 3.10 --seed
uv sync --group dev

# 一键 lint（ruff 代码风格 + docstring + pyright 类型检查）
make lint
# 等价手动命令：
python -m ruff check src tests
python -m pyright src/image_gallery

# 运行测试
make test
# 等价手动命令：
uv run --group test pytest -q

# lint + test 全量检查
make check

# 运行单个测试文件
uv run --group test pytest tests/unit/cleaning/test_specific.py
```

**注意**：Windows 用户如未安装 GNU Make，可直接使用等价手工命令。`pyright` 类型检查中 warning 不阻断，error 阻断。

创建 git worktree 时，继续复用原仓库的 `.venv` 作为开发与验证环境，不要在 worktree 内重新创建独立虚拟环境。

## 编码风格与命名约定

使用 Python 3.10、`src/` 布局、4 空格缩进，并保持 Google 风格的可读性。公开包名和代码命名使用英文与 snake_case。算子命名采用能力优先形式，例如 `quality.blur_check` 或 `duplicate.near_duplicate_check`；OpenCV、fastdup、CleanVision 等后端选择保持为内部实现细节。

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

测试和 Notebook 验证应优先复用 `notebooks/_helpers/` 中已有的路径、存储、数据集和清洗配置入口，避免在测试里重复编写项目根目录定位、MinIO 初始化、默认数据集加载或算子配置样板代码。测试功能行为需要使用真实数据集时，统一复用 `notebooks/_helpers/datasets.py` 提供的默认数据集加载入口，例如 `load_default_minio_sample_1000_dataset()` 或 `load_default_minio_sample_1000_frame()`；不要在测试或 Notebook 验证中临时自造一套功能测试数据集。

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

必须遵循 Conventional Commits 格式，scope 为必填项：

```text
<type>(<scope>): <description>
```

**type**：`feat` | `fix` | `chore` | `refactor` | `test` | `docs` | `style`

**scope**（可用值）：`storage` | `dataset` | `schemas` | `state` | `importers` | `cleaning` | `operators` | `visualization` | `reports` | `utils` | `infra` | `docs`

- description 首字母小写（除非首词是专有名词如 `Azure`、`OpenAI` 或代码实体名）
- 代码实体名（类、函数、参数）用反引号包裹，专有名词不包裹

示例：

```text
feat(cleaning): add resume from checkpoint support
fix(storage): handle missing bucket on connect
chore(cleaning): update test dependencies
feat(operators): `ls_agent_type` tag on `create_agent` calls
docs(infra): update development setup guide
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

行为规范以 `openspec/specs/` 为准。原始设计文档（PRD、架构、开发计划）已备份至 `docs-backup.tar.gz`。

| 目录 | 状态 | 说明 |
|------|------|------|
| `docs/superpowers/` | 参考 | 最新设计规格和实现计划，作为新开发参考 |
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
