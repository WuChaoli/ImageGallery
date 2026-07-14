# 本地测试样本分层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将默认 pytest 的真实图片清洗输入从 MinIO `sample_1000` 切换为仓库内固定的本地 `sample_10`，同时保留显式慢速真实数据验收。

**Architecture:** 测试专用 helper 负责把 fixture Parquet 中的相对图片引用解析成当前 checkout 的绝对 `file://` URI，并在 pytest 临时目录生成运行时 Dataset。默认集成测试只消费该 helper；原 `sample_1000` loader 保持不变，仅供带 `slow`、`real_dataset` marker 的验收测试和 Notebook 使用。

**Tech Stack:** Python 3.10、pytest、pytest-xdist、pytest-socket、pandas/pyarrow、Pillow、现有 Dataset/BasicCleaner API。

## Global Constraints

- 固定样本数量 MUST 为 10，抽样种子 MUST 为 `random_state=20260706`。
- 提交的 fixture MUST NOT 包含生成机器绝对路径、MinIO 凭据或衍生清洗产物。
- 默认测试 MUST NOT 连接 MinIO；生产 `src/` API MUST NOT 因此变更。
- 特定边界行为继续使用专用确定性输入，不依赖随机 sample_10 的内容分布。
- 当前工作区存在其他修改；每次提交只暂存本计划明确列出的文件。

---

## 文件结构

- Create: `tests/helpers/__init__.py` — 测试 helper 包入口。
- Create: `tests/helpers/sample_dataset.py` — fixture 路径解析、运行时本地 URI 物化和 Dataset 加载。
- Create: `tests/fixtures/sample_10/raw.parquet` — 10 条固定记录，图片引用为 `images/` 下文件的相对路径。
- Create: `tests/fixtures/sample_10/images/*` — 10 张固定本地图片。
- Create: `tools/generate_sample_10_fixture.py` — 从当前 sample_1000 可审计地重新生成 fixture。
- Create: `tests/unit/helpers/test_sample_dataset.py` — sample_10 的数量、可移植性、可读性和稳定性契约。
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py` — 默认 StateGraph 验收改用 sample_10；文件重命名为 `test_cleaner_runtime_stategraph_local_dataset.py`。
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py` — first-batch 默认路径改用 sample_10。
- Create: `tests/integration/cleaning/test_cleaner_runtime_sample_1000.py` — 保留最小的真实 MinIO/规模验收。
- Create: `tests/unit/infra/test_pytest_test_layers.py` — marker 与 Makefile 命令契约。
- Modify: `pyproject.toml` — 注册 marker 并默认排除 slow。
- Modify: `Makefile` — 增加 `test_real`、`test_all`，默认 `test` 排除 slow。
- Modify: `AGENTS.md` — 更新测试命令和数据分层规则。

### Task 1: 建立可移植的 sample_10 fixture

**Interfaces:**

- Produces: `get_sample_10_fixture_path() -> Path`
- Produces: `load_sample_10_frame() -> pd.DataFrame`
- Produces: `materialize_sample_10_dataset(output_dir: Path) -> Dataset`
- Consumes: `Dataset.write(...)`、`make_file_image_uri(...)`

- [ ] **Step 1: 编写失败的 fixture helper 契约测试**

创建 `tests/unit/helpers/test_sample_dataset.py`，首先覆盖以下行为：

```python
from pathlib import Path

from tests.helpers.sample_dataset import (
    get_sample_10_fixture_path,
    load_sample_10_frame,
    materialize_sample_10_dataset,
)


def test_sample_10_fixture_has_stable_local_records(tmp_path: Path) -> None:
    fixture_path = get_sample_10_fixture_path()
    frame = load_sample_10_frame()

    assert fixture_path == Path(__file__).parents[2] / "fixtures" / "sample_10" / "raw.parquet"
    assert len(frame) == 10
    assert frame["image_id"].is_unique
    assert all(str(uri).startswith("images/") for uri in frame["image_uri"])
    assert not any("s3://" in str(uri) for uri in frame["image_uri"])

    dataset = materialize_sample_10_dataset(tmp_path)
    materialized = dataset.to_frame()
    assert len(materialized) == 10
    assert dataset.storage is None
    assert all(image.read_bytes() for image in dataset.images())


def test_sample_10_materialization_is_independent_of_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    dataset = materialize_sample_10_dataset(tmp_path / "runtime")
    assert len(dataset.to_frame()) == 10
    assert all(image.read_image().width > 0 for image in dataset.images())
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `uv run pytest tests/unit/helpers/test_sample_dataset.py -q`

Expected: collection FAIL，原因是 `tests.helpers.sample_dataset` 尚不存在，而不是环境或 MinIO 错误。

- [ ] **Step 3: 实现最小测试 helper**

创建 `tests/helpers/__init__.py` 和 `tests/helpers/sample_dataset.py`。实现原则：读取提交的 fixture Parquet，逐行把 `images/...` 解析到 fixture 根目录，用 `make_file_image_uri(fixture_root, relative_uri)` 生成本地 URI，再通过 `Dataset.write` 写入 pytest 的 `output_dir/raw.parquet`。

```python
from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.storage.uri import make_file_image_uri

SAMPLE_10_SIZE = 10


def get_sample_10_fixture_path() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "sample_10" / "raw.parquet"


def load_sample_10_frame() -> pd.DataFrame:
    return pd.read_parquet(get_sample_10_fixture_path())


def materialize_sample_10_dataset(output_dir: Path) -> Dataset:
    fixture_path = get_sample_10_fixture_path()
    frame = load_sample_10_frame().copy()
    frame["image_uri"] = frame["image_uri"].map(
        lambda uri: make_file_image_uri(fixture_path.parent, str(uri))
    )
    return Dataset.write(cast(pd.DataFrame, frame), str(output_dir / "raw.parquet"))
```

- [ ] **Step 4: 编写并运行一次性 fixture 生成器**

创建 `tools/generate_sample_10_fixture.py`。它必须：

1. 调用 `load_default_minio_sample_1000_frame()` 并执行 `.sample(n=10, random_state=20260706)`；
2. 使用 `load_default_minio_sample_1000_dataset().read_image_bytes(image_uri)` 获取每张图片；
3. 使用稳定序号与原扩展名生成 `images/000-<image_id>.<ext>` 文件名；
4. 把 `image_uri` 改为 POSIX 相对路径；
5. 保留 `source_uri` 追溯原引用，但不得写入凭据；
6. 写出前清空的目标仅限已验证的 `tests/fixtures/sample_10/`；
7. 打印抽中的 image_id、文件数量和总字节数。

Run: `uv run python tools/generate_sample_10_fixture.py`

Expected: 生成一个 10 行 Parquet 和恰好 10 张可由 Pillow 打开的图片。

- [ ] **Step 5: 运行 helper 测试并确认 GREEN**

Run: `uv run pytest tests/unit/helpers/test_sample_dataset.py -q --disable-socket`

Expected: PASS；MinIO 不可用也不影响测试。

- [ ] **Step 6: 检查 fixture 可移植性并提交**

Run:

```powershell
uv run python -c "import pandas as pd; f=pd.read_parquet('tests/fixtures/sample_10/raw.parquet'); assert len(f)==10; assert f.image_uri.str.startswith('images/').all(); assert not f.image_uri.str.contains('s3://|^[A-Za-z]:', regex=True).any()"
git diff --check -- tests/helpers tests/fixtures tools/generate_sample_10_fixture.py tests/unit/helpers
```

Commit only these files with: `测试：添加固定本地测试样本`

### Task 2: 默认清洗集成测试迁移到 sample_10

**Interfaces:**

- Consumes: `materialize_sample_10_dataset(output_dir: Path) -> Dataset`
- Consumes: `SAMPLE_10_SIZE = 10`
- Produces: 默认 StateGraph、TOML recipe、first-batch 测试全部无 MinIO 依赖。

- [ ] **Step 1: 先改断言和 fixture 引用并确认 RED**

将 StateGraph 文件重命名为 `test_cleaner_runtime_stategraph_local_dataset.py`，把 fixture 改为：

```python
@pytest.fixture(scope="module")
def sample_10_dataset(tmp_path_factory: pytest.TempPathFactory):
    return materialize_sample_10_dataset(tmp_path_factory.mktemp("sample-10-stategraph"))
```

将测试名、label、tag 和数量断言统一从 `sample_1000`/1000 改为 `sample_10`/`SAMPLE_10_SIZE`。first-batch 测试使用 `materialize_sample_10_dataset(tmp_path)`，删除 `load_minio_storage`、`StorageConnectionError` 和 skip 分支。

Run:

```powershell
uv run pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_local_dataset.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q --disable-socket
```

Expected: 在 helper import/fixture 尚未完整接入时 FAIL，失败点明确指向 sample_10 装配。

- [ ] **Step 2: 完成最小迁移并确认 GREEN**

保持现有 StateGraph 产物、preview、resume、SQLite 和 operator columns 断言，仅替换数据来源与数量契约。不得删除 `_two_image_dataset`、`test_basic_cleaner_runs_first_batch_builtin_operators` 等专用边界测试。

Run: 同 Step 1。

Expected: 全部 PASS，pytest-socket 没有报告网络访问。

- [ ] **Step 3: 检查迁移文件不再引用 MinIO 并提交**

Run:

```powershell
rg -n "sample_1000|load_minio_storage|StorageConnectionError|s3://" tests/integration/cleaning/test_cleaner_runtime_stategraph_local_dataset.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py
```

Expected: 默认 sample 路径无匹配；专用测试的普通字符串不计入外部依赖。

Commit with: `测试：迁移默认清洗验收到本地样本`

### Task 3: 保留 sample_1000 慢速真实验收

**Interfaces:**

- Consumes: `load_default_minio_sample_1000_dataset()`、`load_default_minio_sample_1000_frame()`。
- Produces: 同时带 `slow` 和 `real_dataset` marker 的独立验收文件。

- [ ] **Step 1: 编写 marker 尚未注册时的失败测试**

创建 `tests/integration/cleaning/test_cleaner_runtime_sample_1000.py`，文件级声明：

```python
pytestmark = [pytest.mark.slow, pytest.mark.real_dataset]
```

保留最小但有区分度的验收：1000 行契约、真实图片可读取、非语义配置 dry-run，以及一条完整 first-batch 或 non-semantic 清洗。MinIO/数据不可用时用明确原因 `pytest.skip()`。

Run: `uv run pytest tests/integration/cleaning/test_cleaner_runtime_sample_1000.py --collect-only -q`

Expected: collection 产生 `PytestUnknownMarkWarning` 或严格 marker 配置下 FAIL。

- [ ] **Step 2: 暂时通过 CLI 注册 marker 并验证测试边界**

Run:

```powershell
uv run pytest -o markers="slow: tests requiring large datasets" -o markers="real_dataset: tests requiring sample_1000 and MinIO" -m real_dataset tests/integration/cleaning/test_cleaner_runtime_sample_1000.py --collect-only -q
```

Expected: 只收集该文件内的真实数据验收。

- [ ] **Step 3: 提交真实验收文件**

Commit with: `测试：保留千张真实数据慢速验收`

### Task 4: 配置 pytest 和 Makefile 测试分层

**Interfaces:**

- Produces: `make test` = `-m "not slow"`。
- Produces: `make test_real` = `-m "real_dataset"`。
- Produces: `make test_all` = 不附带默认 `-m "not slow"` 的完整收集。

- [ ] **Step 1: 编写失败的配置契约测试**

创建 `tests/unit/infra/test_pytest_test_layers.py`，读取 `pyproject.toml` 和 Makefile，断言：

```python
def test_pytest_registers_and_excludes_slow_tests_by_default() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = config["tool"]["pytest"]["ini_options"]
    assert pytest_config["addopts"] == '-m "not slow"'
    assert any(marker.startswith("slow:") for marker in pytest_config["markers"])
    assert any(marker.startswith("real_dataset:") for marker in pytest_config["markers"])


def test_makefile_exposes_default_real_and_all_test_targets() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "test_real:" in makefile
    assert "-m real_dataset" in makefile
    assert "test_all:" in makefile
    assert "-o addopts=" in makefile
```

Run: `uv run pytest tests/unit/infra/test_pytest_test_layers.py -q`

Expected: FAIL，因为 `addopts`、marker 和两个 Make target 尚不存在。

- [ ] **Step 2: 最小配置实现**

在 `pyproject.toml` 的 pytest 配置加入：

```toml
addopts = '-m "not slow"'
markers = [
  "slow: tests requiring large datasets or long-running processing",
  "real_dataset: tests requiring sample_1000 and MinIO",
]
```

Makefile 中：默认 `test` 继承 addopts；`test_real` 使用 `-o addopts= -m real_dataset`；`test_all` 使用 `-o addopts=`。三个命令都保留 xdist 和 socket 参数；如真实验收有共享目录冲突，将 `test_real` 固定为 `-n 0`。

- [ ] **Step 3: 验证 marker 收集边界**

Run:

```powershell
uv run pytest --collect-only -q
uv run pytest -o addopts= -m real_dataset --collect-only -q
uv run pytest -o addopts= --collect-only -q
```

Expected: 默认不包含 sample_1000 文件；第二条仅包含 real_dataset；第三条同时包含两层。

- [ ] **Step 4: 更新 AGENTS.md**

在构建测试命令和测试指南中明确：默认功能测试使用 `tests/fixtures/sample_10`；Notebook/真实验收继续使用 sample_1000；提供 `make test`、`make test_real`、`make test_all` 及直接 `uv run` 等价命令。

- [ ] **Step 5: 运行配置测试并提交**

Run: `uv run pytest tests/unit/infra/test_pytest_test_layers.py -q`

Expected: PASS。

Commit with: `优化：分层默认测试与真实数据验收`

### Task 5: 全量验证与耗时对比

**Interfaces:** 无新增接口；本任务只验证完成状态并同步 OpenSpec task checkbox。

- [ ] **Step 1: 运行定向无网络测试**

Run:

```powershell
uv run pytest tests/unit/helpers/test_sample_dataset.py tests/integration/cleaning/test_cleaner_runtime_stategraph_local_dataset.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q --disable-socket --durations=20
```

Expected: PASS，无 socket 错误，三条原慢路径均只处理 10 张图片。

- [ ] **Step 2: 运行默认完整测试并记录耗时**

Run: `uv run pytest -q --disable-socket --durations=20`

Expected: 默认测试全部 PASS，sample_1000 未收集；总耗时显著低于改造前串行基线 404.49 秒。

- [ ] **Step 3: 运行并行仓库入口**

Run: `make test`

Equivalent: `uv run pytest -n auto --disable-socket --allow-unix-socket -m "not slow" tests/`

Expected: PASS。

- [ ] **Step 4: 验证真实数据入口**

Run: `make test_real`

Equivalent: `uv run pytest -o addopts= -m real_dataset --disable-socket tests/`

Expected: MinIO 可用则 PASS；不可用则以明确原因 SKIP，不得因 fixture 或 marker 配置失败。

- [ ] **Step 5: 静态检查和 OpenSpec 状态同步**

Run:

```powershell
uv run ruff check tests tools
uv run pyright src/image_gallery
openspec validate optimize-pytest-sample-dataset --strict
git diff --check
```

Expected: 全部通过；随后把 `tasks.md` 已完成项更新为 `[x]`，但不归档 change，归档由 finish-development 流程统一执行。

- [ ] **Step 6: 提交验证与文档同步**

Commit with: `文档：同步本地测试样本实施状态`
