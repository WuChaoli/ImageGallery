# pHash 近重复清洗算子设计

## 背景

当前清洗 v3 已经支持 `duplicate.exact_duplicate_check`。该算子通过 `content_hash` 判断原始字节完全一致的图片，并在 `dataset_aggregate` 阶段生成完全重复组。

下一步需要补充视觉层面的重复检测：两张图片即使编码、尺寸或压缩参数不同，只要视觉内容足够接近，也可以被识别为重复。第一版先实现轻量 `pHash` 近重复，不引入 CLIP、YOLO、ANN index 或外部去重框架。

## 目标

1. 新增用户侧逻辑算子 `duplicate.perceptual_duplicate_check`。
2. 使用 `Pillow + numpy` 自实现轻量 DCT pHash，不新增运行依赖。
3. 复用现有 planner/scheduler：先在 `per_image` 阶段计算 `phash`，再在 `dataset_aggregate` 阶段生成近重复组。
4. 第一版只做二分决策：命中阈值的非首图 `drop`，其余 `keep`，不提供 `review` 档。
5. 与 `duplicate.exact_duplicate_check` 并存，语义上保持完全重复和视觉近重复分离。

## 非目标

1. 不实现 `duplicate.near_duplicate_check` 这个泛化名称，避免与后续 embedding、fastdup 或 ANN 方案混淆。
2. 不引入 `imagehash`、fastdup、CLIP、YOLO、Faiss、Milvus 等新依赖。
3. 不做跨 run 缓存、索引持久化、增量去重或超大数据集优化。
4. 不做人工复核分档；第一版只输出 `drop` 或 `keep`。
5. 不改变现有 `duplicate.exact_duplicate_check` 的行为和默认配置。

## 用户侧算子

```python
BasicCleaner(
    [
        {"duplicate.perceptual_duplicate_check": {}},
    ]
)
```

默认配置：

```python
{
    "max_distance": 4,
    "keep": "first",
    "action": "drop",
}
```

配置语义：

1. `max_distance`：pHash Hamming distance 小于等于该值时，认为足够相似，可以删除非首图。
2. `keep`：第一版只支持 `"first"`，表示每个近重复组保留 `parameter_table` 顺序中的第一张。
3. `action`：第一版只支持 `"drop"`，表示命中阈值的非首图进入删除结果。

## 参数计算链路

### ImagePerceptualHashComputer

执行模式：`per_image`

产出参数：

```text
phash
```

输入来自 `ImageBatchItem.image`。如果图片读取或解码失败，`phash` 输出为空字符串。

pHash 算法第一版使用标准轻量流程：

1. 将图片转为灰度图。
2. 缩放到固定小尺寸，例如 `32x32`。
3. 对灰度矩阵做二维 DCT。
4. 取左上角低频区域，例如 `8x8`。
5. 去掉直流分量后按中位数生成 64 位二进制 hash。
6. 将结果编码为 16 位十六进制字符串。

二维 DCT 通过 numpy 矩阵乘法实现，不依赖 scipy。

### PerceptualDuplicateGroupComputer

执行模式：`dataset_aggregate`

依赖参数：

```text
phash
```

产出参数：

```text
perceptual_duplicate_group_id
perceptual_duplicate_count
perceptual_duplicate_distance
```

分组规则：

1. 忽略空 `phash`。
2. 按 `parameter_table` 的现有顺序扫描图片。
3. 当前图片与已有组的 keeper 比较 Hamming distance。
4. 若最小距离 `<= max_distance`，加入该组。
5. 若没有命中任何已有组，则创建新组并以当前图片作为 keeper。
6. 只有组内数量大于 1 的图片才写入非空 `perceptual_duplicate_group_id`。
7. keeper 的 `perceptual_duplicate_distance` 为 `0`，重复成员记录与 keeper 的距离。

第一版采用朴素两两比较，适合当前本地 Notebook 和小中型数据集验证。后续如需优化，可以在不改变逻辑算子契约的前提下替换分组实现。

## 评估逻辑

`duplicate.perceptual_duplicate_check` 的 required parameters：

```text
perceptual_duplicate_group_id
perceptual_duplicate_count
perceptual_duplicate_distance
```

evaluation columns：

```text
perceptual_duplicate_group_id
perceptual_duplicate_count
perceptual_duplicate_distance
perceptual_duplicate_action
perceptual_duplicate_reason
```

评估规则：

1. `keep` 不是 `"first"` 时抛出明确错误。
2. `action` 不是 `"drop"` 时抛出明确错误。
3. 没有近重复组，或者组数量为 1：输出 `keep`。
4. 每个近重复组第一次出现的图片：输出 `keep`。
5. 同组后续图片：输出 `drop`，reason 包含 group id 和 distance。

## Relation 产物

新增 relation table：

```text
relations/perceptual_duplicate_pairs.parquet
```

字段沿用现有 relation 表风格：

```text
relation_type
source_image_id
target_image_id
score
group_id
parameter_name
computer_name
artifact_ref
created_at
```

约定：

1. `relation_type` 使用 `perceptual_duplicate`。
2. `source_image_id` 是 keeper。
3. `target_image_id` 是被判定为近重复的成员。
4. `score` 使用 `1 - distance / 64`。
5. `parameter_name` 使用 `perceptual_duplicate_group_id`。
6. `computer_name` 使用 `perceptual_duplicate_group_computer`。

## 文件影响

预计修改：

```text
src/image_gallery/operators/computers/hash.py
src/image_gallery/operators/computers/duplicate.py
src/image_gallery/operators/builtin.py
tests/unit/operators/test_hash_computer.py
tests/unit/operators/test_duplicate_computer.py
tests/unit/operators/test_builtin_specs.py
tests/integration/cleaning/test_basic_cleaner_builtin_run.py
notebooks/_helpers/cleaning_configs.py
```

如实现过程中发现 Notebook helper 或集成测试不需要调整，可以保持不动。

## 测试策略

1. `ImagePerceptualHashComputer`：
   - 相同图片多次计算得到相同 `phash`。
   - 输出为 16 位十六进制字符串。
   - 解码失败图片输出空 `phash`。
2. `PerceptualDuplicateGroupComputer`：
   - Hamming distance `<= max_distance` 的图片进入同组。
   - 距离超过阈值的图片保持唯一。
   - relation table 记录 keeper 到重复成员的 pair。
3. evaluator：
   - 同组第一张 `keep`，后续图片 `drop`。
   - 非法 `keep` 或 `action` 配置抛错。
4. registry：
   - 默认 registry 包含 `duplicate.perceptual_duplicate_check`。
   - planner 能从该逻辑算子展开到 `phash` 和近重复组 computer。
5. 回归验证：
   - 现有 exact duplicate 测试不变。
   - 运行 operator 和 cleaning 相关单元/集成测试。

## 成功标准

1. `BasicCleaner([{"duplicate.perceptual_duplicate_check": {}}]).compile()` 能生成 `per_image -> dataset_aggregate` 的执行计划。
2. 运行后 `parameter_table.parquet` 包含 `phash` 和 `perceptual_duplicate_*` 参数。
3. 运行后 `evaluation_table.parquet` 包含 `perceptual_duplicate_action` 和 `perceptual_duplicate_reason`。
4. 对于视觉近似且距离 `<= 4` 的非首图，最终 action 为 `drop`。
5. `relations/perceptual_duplicate_pairs.parquet` 被写出。
6. `pytest`、`ruff` 和 `mypy` 在相关范围内通过。
