# 阶段 3/4 算子 Notebook 验收设计

## 目标

新增一个 Notebook，用于人工验收阶段 3 清洗平台核心能力和阶段 4 内置基础算子能力。Notebook 复用导入阶段已经生成的 raw Dataset：

```text
notebooks/.importers_test_library/outputs/raw.parquet
```

Notebook 输出放在：

```text
notebooks/.operators_test_library/
```

## 非目标

1. 不重新生成 raw Dataset。
2. 不测试 importer 流程。
3. 不测试 `duplicate.near_duplicate_check` 的 fastdup 真实能力。
4. 不测试 Notebook 图片网格或静态 HTML 报告。
5. 不把输出写入项目根目录。

## Notebook 文件

```text
notebooks/operators_builtin_test.ipynb
```

## Notebook 结构

### 1. 环境与路径

导入 `Path`、`pandas`、`Dataset` 和 `BasicCleaner`。

定义：

```text
RAW_DATASET_PATH = notebooks/.importers_test_library/outputs/raw.parquet
OUTPUT_DIR = notebooks/.operators_test_library/outputs
```

如果 raw Dataset 不存在，单元格应直接抛出明确错误，提示先运行导入测试 Notebook 或导入示例。

### 2. 读取 raw Dataset

使用 `Dataset.from_path()` 加载 raw Dataset，并显示：

1. 行数。
2. 字段列表。
3. 前几行。

断言 raw Dataset 至少包含：

```text
image_id
image_uri
```

### 3. 运行 BasicCleaner

启用阶段 4 已实现的基础内置算子：

```text
format.decode_check
size.dimension_check
quality.blur_check
quality.brightness_check
quality.contrast_check
duplicate.exact_duplicate_check
```

不启用：

```text
duplicate.near_duplicate_check
```

原因：fastdup 是可选依赖边界，当前 Notebook 只验收不依赖重型第三方服务的基础链路。

### 4. 验收阶段 3 清洗平台核心

展示并断言：

1. `parameter_table.parquet` 已生成。
2. `evaluation_table.parquet` 已生成。
3. `operator_outputs.yaml` 已生成。
4. `state.json` 已生成。
5. `cleaner.state()` 能展示算子状态矩阵。
6. `cleaner.preview()` 能返回 clean、review、dropped、restricted 统计。
7. `cleaner.result(operator_name)` 只返回该算子的评估列。
8. `cleaner.export()` 能导出 `full`、`clean`、`review`、`dropped`、`parameters`、`evaluations`。

### 5. 验收阶段 4 内置算子

读取 `parameter_table`，断言至少存在以下参数列：

```text
width
height
decode_ok
decode_error
blur_score
brightness_score
contrast_score
content_hash
phash
exact_duplicate_group_id
```

读取 `evaluation_table`，断言至少存在：

```text
decode_action
decode_reason
dimension_action
dimension_reason
blur_action
blur_reason
brightness_action
brightness_reason
contrast_action
contrast_reason
exact_duplicate_action
exact_duplicate_reason
final_action
final_reason
triggered_operator_names
```

Notebook 不强制要求每个算子都必须命中异常，因为 raw Dataset 的图片内容来自导入测试数据，内容可能随样本变化。验收重点是算子能运行、字段能生成、结果能导出。

### 6. 验证 config/rerun

选择一个不依赖重新计算参数的配置变化，例如调整 `quality.blur_check` 的阈值。

验证：

1. 调用 `cleaner.config()` 后，`cleaner.state()` 中对应算子状态变为 `stale`。
2. 调用 `cleaner.rerun()` 后，对应算子状态回到 `completed`。
3. `evaluation_table` 和 `final_action` 可重新生成。

不要求 Notebook 证明 backend 没有被重新调用；这个行为由单元测试覆盖。

### 7. 导出一致性

导出：

```text
full.parquet
clean.parquet
review.parquet
dropped.parquet
parameters.parquet
evaluations.parquet
```

断言：

```text
full_count == clean_count + review_count + dropped_count + restricted_count
```

其中 `restricted_count` 来自 `preview()`，第一版不单独导出 restricted Dataset。

### 8. 最终输出

最后一个单元格输出：

```text
PASS: stage3 and stage4 operator validation completed
```

## 错误处理

1. raw Dataset 缺失：直接报错，并提示目标路径。
2. raw Dataset 缺少 `image_id` 或 `image_uri`：直接断言失败。
3. 任一关键产物缺失：断言失败。
4. 任一关键字段缺失：断言失败。
5. fastdup 不可用不视为失败，因为 Notebook 不启用 near duplicate 算子。

## 测试方式

实现后至少运行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m mypy src/image_gallery
```

Notebook 本身可通过 Jupyter 手动运行验证。若项目后续加入 notebook 执行工具，可追加自动执行验证。
