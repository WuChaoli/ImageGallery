# 清洗 v3 sample_1000 Notebook 验证设计

## 背景

当前仓库已经完成清洗 v3 第一批算子的核心实现与集成测试，且默认 MinIO 测试数据集已经提供了稳定的真实样本：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
```

后续 Notebook 验证、调参和人工分析都会反复使用两类公共前置能力：

1. 基于 `.env` 初始化 `MinioStorage`。
2. 基于 sample_1000 的 raw Dataset 初始化 `Dataset` 和 raw dataframe。

如果把这些逻辑分散写在每个 Notebook 中，后续会出现路径、环境变量、输出目录和算子配置各自维护的问题。因此本设计将这部分共性逻辑前置到 `notebooks/_helpers/`，再新增一个专门面向 sample_1000 的清洗 v3 分析型验证 Notebook。

## 目标

1. 新增一个专门的 Notebook，用于验证 `sample_1000/raw.parquet + MinIO + 清洗 v3 第一批算子`。
2. 将 MinIO storage 初始化、sample_1000 Dataset 初始化、路径管理和第一批算子配置提取为 Notebook 可复用 helper。
3. 让后续 Notebook 直接 import helper，而不是重复编写 `.env`、路径和数据集装配逻辑。
4. Notebook 既验证闭环能跑通，也提供结构化产物检查、统计汇总和重点样本抽样能力。
5. 保持边界清晰：helper 负责初始化和轻量装配，Notebook 负责组装、运行和展示，不引入新的公共业务 API。

## 非目标

1. 不修改 `ImportPipeline`、`Dataset`、`MinioStorage`、`BasicCleaner` 或 operator 的公共行为。
2. 不重新生成默认 MinIO 数据集。
3. 不把 Notebook 抽象成通用测试框架或一站式执行器。
4. 不在第一版引入图片网格、HTML 报告或 Web UI。
5. 不实现 `.env` 缺失时的降级模式；本 Notebook 强依赖 MinIO。
6. 不自动执行 Notebook 作为 CI 测试；自动化覆盖以 helper 单测和现有集成测试为主。

## 文件与职责

### 1. 新增 Notebook helper 目录

```text
notebooks/_helpers/
```

该目录只服务于 Notebook 与轻量测试脚本，不放入 `src/image_gallery/`，避免把验证期便利性工具升级为正式产品 API。

### 2. 新增 helper 文件

```text
notebooks/_helpers/paths.py
notebooks/_helpers/storage.py
notebooks/_helpers/datasets.py
notebooks/_helpers/cleaning_configs.py
```

### 3. 新增 Notebook

```text
notebooks/cleaning_v3_sample_1000_test.ipynb
```

该 Notebook 是 sample_1000 的分析型验证入口，不替换现有：

```text
notebooks/operators_builtin_test.ipynb
```

也不恢复旧的本地 synthetic fixture Notebook。最小闭环验证继续由单元测试和集成测试承担；这个新 Notebook 只负责真实 sample 数据集的人工分析验证。

## Helper 设计

### paths.py

职责：

1. 统一定位仓库根目录。
2. 统一管理 Notebook 私有运行目录。
3. 统一清理本次运行输出目录。

最小接口：

```python
def get_repo_root() -> Path: ...
def get_notebook_library_root(name: str) -> Path: ...
def reset_output_dir(path: Path) -> Path: ...
```

约束：

1. `get_repo_root()` 沿用当前 Notebook 的探测习惯：优先 `Path.cwd()`，若当前目录不是仓库根，则回退到父目录，并要求能找到 `pyproject.toml`。
2. `get_notebook_library_root(name)` 统一返回：

```text
notebooks/.operators_test_library/<name>/
```

或等价 notebook 私有目录，避免把运行产物散落到项目根目录。
3. `reset_output_dir(path)` 应删除并重建目录，保证每次 Notebook 运行结果不混入旧产物。

### storage.py

职责：

1. 统一加载仓库根目录 `.env`。
2. 校验 MinIO 必填环境变量。
3. 返回已连接的 `MinioStorage`。

最小接口：

```python
def read_required_env(name: str) -> str: ...
def load_minio_storage() -> MinioStorage: ...
```

依赖环境变量：

```text
IMAGE_GALLERY_MINIO_ENDPOINT
IMAGE_GALLERY_MINIO_ACCESS_KEY
IMAGE_GALLERY_MINIO_SECRET_KEY
IMAGE_GALLERY_MINIO_BUCKET
```

约束：

1. 缺少任一环境变量时直接报错，并指出变量名。
2. endpoint 解析规则与现有 MinIO Notebook 保持一致：从完整 URL 中拆出 `endpoint` 与 `secure`。
3. helper 只返回已连接 storage，不处理 Dataset 或 object path。

### datasets.py

职责：

1. 统一定位 default MinIO sample_1000 raw Dataset。
2. 基于 `load_minio_storage()` 构建带 storage 的 `Dataset`。
3. 提供直接读取 dataframe 的入口，方便 Notebook 先检查输入表。

最小接口：

```python
def get_default_minio_sample_1000_raw_path() -> Path: ...
def load_default_minio_sample_1000_dataset() -> Dataset: ...
def load_default_minio_sample_1000_frame() -> pd.DataFrame: ...
```

路径约定：

```text
notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
```

约束：

1. `raw.parquet` 缺失时直接失败。
2. `load_default_minio_sample_1000_dataset()` 必须返回绑定了 MinIO storage 的 `Dataset`，而不是纯本地 parquet reader。
3. `load_default_minio_sample_1000_frame()` 只负责表读取，不做清洗逻辑。

### cleaning_configs.py

职责：

1. 统一维护清洗 v3 第一批算子配置。
2. 让 Notebook、轻量测试脚本和后续分析入口共用同一套配置源。

最小接口：

```python
def get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]: ...
```

第一版包含的算子以当前第一批实现为准，至少覆盖：

```text
format.decode_check
size.dimension_check
size.aspect_ratio_check
size.megapixel_check
quality.blur_check
quality.brightness_check
quality.contrast_check
content.blank_image_check
duplicate.exact_duplicate_check
```

约束：

1. Notebook 不再在单元格中手写整套算子配置。
2. helper 中的配置应与当前集成测试保持一致，避免 Notebook 和测试出现两套语义漂移。

## 可复用边界

第一版只抽取高复用、低争议的公共部分：

1. 路径定位。
2. `.env` 与 MinIO storage 初始化。
3. sample_1000 raw Dataset 初始化。
4. 第一批算子配置。

暂不抽取以下内容：

1. `run_cleaner_and_analyze()` 这类一站式执行函数。
2. 统计汇总与样本抽样 helper。
3. 图片展示排版 helper。
4. 通用 Notebook testing framework。

原因：

1. 当前最稳定的复用需求是“初始化”，不是“分析视图”。
2. 统计和展示逻辑仍可能随 Notebook 目标变化而调整，过早抽象会把后续 notebook 写死。
3. `BasicCleaner` 运行和结果分析应在 Notebook 中显式展开，方便人工理解与调试。

## Notebook 结构

Notebook 文件：

```text
notebooks/cleaning_v3_sample_1000_test.ipynb
```

推荐结构如下。

### 1. 说明、环境与路径

说明这是一个强依赖 MinIO 的分析型验证 Notebook，目标是基于 sample_1000 数据集验证清洗 v3 第一批算子。

导入：

1. `pandas`
2. `BasicCleaner`
3. `Dataset`
4. `notebooks._helpers.paths`
5. `notebooks._helpers.storage`
6. `notebooks._helpers.datasets`
7. `notebooks._helpers.cleaning_configs`

同时初始化 notebook 私有输出目录，例如：

```text
notebooks/.operators_test_library/cleaning_v3_sample_1000/
```

### 2. 输入表检查

通过 helper 读取 `sample_1000/raw.parquet`，展示：

1. 总行数。
2. 字段列表。
3. 前几行。
4. `image_uri` 是否为空。
5. `image_id` 是否重复。

这一步的目的是先确认输入表本身可读且结构合理，再进入图片读取与清洗阶段。

### 3. MinIO storage 与 Dataset 初始化

通过 helper：

1. 读取 `.env`
2. 初始化并连接 `MinioStorage`
3. 构建带 storage 的 `Dataset`

然后抽样读取 1 到 3 张图片，确认远端读图链路可用。任一图片读取失败都直接报错，不做跳过。

### 4. 第一批算子配置

通过 helper 获取第一批算子配置，并在 Notebook 中显式展示 operator name 列表，确认本次 run 的配置来源和顺序。

### 5. 运行 BasicCleaner

使用统一配置运行：

```python
cleaner = BasicCleaner(operator_configs)
cleaner.run(dataset, output_dir=run_output_dir)
```

run 输出目录放在 notebook 私有目录内，避免污染其他测试目录。

### 6. 结构化产物检查

读取并展示：

1. `parameter_table.parquet`
2. `evaluation_table.parquet`
3. `state.json`
4. `parameter_manifest.json`
5. `relations/duplicate_pairs.parquet`

至少检查以下事实：

1. `preview()` 能返回总数和 action 分布。
2. `state()` 能返回算子状态矩阵。
3. `parameter_table` 包含关键参数列。
4. `evaluation_table` 包含关键评估列。
5. 完全重复 relation 产物存在。

关键参数列至少包括：

```text
width
height
aspect_ratio
megapixels
blur_score
brightness_score
contrast_score
blank_score
content_hash
exact_duplicate_group_id
exact_duplicate_count
```

关键评估列至少包括：

```text
decode_action
decode_reason
dimension_action
dimension_reason
aspect_ratio_action
aspect_ratio_reason
megapixel_action
megapixel_reason
blur_action
blur_reason
brightness_action
brightness_reason
contrast_action
contrast_reason
blank_action
blank_reason
exact_duplicate_action
exact_duplicate_reason
final_action
final_reason
triggered_operator_names
```

### 7. 统计汇总

Notebook 应提供足够判断整体效果的固定统计视图：

1. `final_action` 分布。
2. 每个算子的触发数量，即对应 `*_action != "keep"` 的数量。
3. 完全重复统计：重复图片数、重复组数、最大组大小。

这些统计只在 Notebook 内完成，不抽到 helper。

### 8. 重点样本抽样

Notebook 应提供人工检查友好的样本表：

1. `keep` 抽样 5 条。
2. `review` 抽样 5 条。
3. `drop` 抽样 5 条。
4. 对 `blank_action`、`exact_duplicate_action`、`dimension_action` 分别展示 3 到 5 条典型命中样本。

每条样本至少展示：

```text
image_id
image_uri
相关参数分数
相关 reason
final_action
```

### 9. 导出验证

至少验证：

1. `full`
2. `dropped`

如果 Notebook 需要，也可以顺手展示 `clean` 或 `review`，但第一版不是硬性要求。

导出验证至少包括：

1. 导出文件存在。
2. 导出行数与 `evaluation_table` 中对应筛选结果一致。
3. 导出结果前几行包含关键列。

## 错误处理

1. `.env` 缺字段时，直接报错并显示变量名。
2. `sample_1000/raw.parquet` 不存在时，直接报错并显示目标路径。
3. MinIO 连接失败时，直接抛出 storage 连接错误。
4. 抽样读图失败时，直接报错并显示失败 `image_uri`。
5. raw dataframe 缺少 `image_id` 或 `image_uri` 时，直接断言失败。
6. 任一关键产物文件缺失时，直接断言失败。
7. 任一关键列缺失时，直接断言失败。
8. Notebook 不提供 fallback 或静默跳过逻辑。

## 测试与验证边界

helper 文件应有对应单元测试，覆盖：

1. 路径定位。
2. 输出目录重置。
3. 环境变量校验。
4. sample_1000 路径定位。
5. 第一批算子配置结构。

Notebook 本身不要求纳入自动化测试执行，但实现时应尽量复用现有集成测试中的 operator 配置与字段断言习惯，减少维护分叉。

## 成功标准

1. `notebooks/_helpers/` 下存在路径、storage、datasets、cleaning_configs 四个 helper 文件。
2. `notebooks/cleaning_v3_sample_1000_test.ipynb` 存在。
3. Notebook 能在 `.env` 正确、MinIO 可用时跑通完整清洗闭环。
4. Notebook 能显式展示输入概览、运行结果总览、结构化产物、统计汇总和重点样本抽样。
5. helper 的职责边界清晰，后续其他 Notebook 可直接复用，不需要复制初始化逻辑。
