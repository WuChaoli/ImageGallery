# 语义去重清洗算子设计

## 背景

当前清洗 v3 已经支持两类去重能力：

1. `duplicate.exact_duplicate_check`：基于 `content_hash` 的字节级完全重复。
2. `duplicate.perceptual_duplicate_check`：基于 pHash 的视觉近重复。

下一步需要加入语义层面的 image-image 去重。语义去重用于识别“内容语义相同或高度相似，但编码、尺寸、裁剪、颜色或构图不一定接近”的图片重复。它应作为独立逻辑算子存在，不改造现有 pHash 算子，也不复用 `perceptual_duplicate_*` 字段。

## 目标

1. 新增用户侧逻辑算子 `duplicate.semantic_duplicate_check`。
2. 默认绑定 `onnx-community/dinov2-small-ONNX` image embedding provider，让用户可以直接运行语义去重。
3. 允许外部注入自定义 embedding provider，用于替换为本地模型、远程服务或企业内部 embedding API。
4. 使用 Faiss ANN index 作为第一版索引能力，并把 embedding 与 index 保存为 cleaning run artifact。
5. 通过 `relations/semantic_duplicate_pairs.parquet` 解释 keeper、duplicate、score 和 index artifact 来源。
6. 默认对语义重复非 keeper 执行 `drop`，并允许用户配置为 `review`。

## 非目标

1. 第一版不接入独立向量数据库，例如 Milvus、Qdrant、Chroma 或 pgvector。
2. 第一版不实现跨 run 向量复用、长期在线检索服务或多数据集向量库同步。
3. 第一版不实现文本检索、caption、OCR、分类、聚类或跨模态搜索能力。
4. 第一版不实现复杂 keeper 选择策略，例如按质量分、分辨率或业务权重选择。
5. 第一版不改变 `duplicate.exact_duplicate_check`、`duplicate.perceptual_duplicate_check`、export 或 preview 的现有语义。

## 用户侧语义

新增逻辑算子：

```python
BasicCleaner(
    [
        {
            "duplicate.semantic_duplicate_check": {
                "threshold": 0.92,
                "keep": "first",
                "action": "drop",
            }
        }
    ]
)
```

默认配置：

```python
{
    "threshold": 0.92,
    "keep": "first",
    "action": "drop",
    "provider": "onnx_dinov2_small",
    "model_id": "onnx-community/dinov2-small-ONNX",
    "index": "faiss_flat_ip",
    "batch_size": 32,
}
```

配置语义：

1. `threshold`：embedding 归一化后，cosine similarity 大于等于该值时认为语义重复。
2. `keep`：第一版只支持 `"first"`，表示每个语义重复组保留 `parameter_table` 顺序中的第一张。
3. `action`：支持 `"drop"` 和 `"review"`。默认 `"drop"`。
4. `provider`：默认使用 `onnx_dinov2_small`，也可以指向外部注入 provider。
5. `index`：第一版支持 `"faiss_flat_ip"`，使用归一化 embedding 与 inner product 近似 cosine similarity。
6. `model_id`：默认使用 `onnx-community/dinov2-small-ONNX`。
7. `batch_size`：provider 批量推理大小。

`duplicate.semantic_duplicate_check` 只表达 image-image 语义重复。它不表达文本检索、caption、OCR、分类或聚类。

## 组件边界

### SemanticEmbeddingProvider

`SemanticEmbeddingProvider` 负责把图片批量转换成归一化 image embedding。

职责：

1. 接收已读取、已解码的图片批次。
2. 返回稳定维度的二维向量数组。
3. 声明 `provider_name`、`provider_version`、`embedding_dimension` 和是否已归一化。

非职责：

1. 不决定重复分组。
2. 不决定 action。
3. 不写 `evaluation_table`。
4. 不写 relation table。

默认 provider 作为 semantic 可选能力启用。主包不应强制安装语义模型依赖。用户未安装 semantic 可选依赖却使用默认 provider 时，应抛出明确错误，提示安装语义可选依赖。

第一版默认 provider 明确为：

```text
provider = "onnx_dinov2_small"
runtime = "onnxruntime"
model_id = "onnx-community/dinov2-small-ONNX"
base_model = "facebook/dinov2-small"
embedding_dimension = 384
embedding_source = "cls_token"
normalize = true
```

该 provider 通过 ONNX Runtime 执行 DINOv2-small ONNX 模型，提取 image-image embedding。模型文件不打入 wheel。首次使用时可以下载到本地 cache；离线环境或受控环境中，用户可以通过 `model_path` 指定已下载的 ONNX 文件。实现必须在 artifact manifest 中记录最终使用的 `model_id`、`model_path`、`base_model` 和 `embedding_dimension`。

外部 provider 注入用于支持本地模型、远程 embedding 服务或企业内部模型。注入方式可以在实现计划中进一步细化，但不应改变 `duplicate.semantic_duplicate_check` 的用户侧算子名称和输出契约。

### SemanticEmbeddingComputer

执行模式：`per_image`

产出参数：

```text
semantic_embedding_ref
```

职责：

1. 调用 `SemanticEmbeddingProvider` 生成 embedding。
2. 校验 embedding 维度、空值、NaN、Inf 和归一化状态。
3. 写出 embedding artifact。
4. 在 `parameter_table` 中写入 `semantic_embedding_ref`。

`parameter_table` 只保存 embedding 引用，不保存高维向量本体。

### SemanticDuplicateGroupComputer

执行模式：`dataset_aggregate`

依赖参数：

```text
semantic_embedding_ref
```

产出参数：

```text
semantic_duplicate_group_id
semantic_duplicate_count
semantic_duplicate_score
semantic_duplicate_nearest_image_id
```

职责：

1. 读取 embedding artifact。
2. 构建 Faiss index artifact。
3. 基于 `threshold` 查找语义重复 pair。
4. 按 `parameter_table` 顺序生成 keeper-first 分组。
5. 写出 `relations/semantic_duplicate_pairs.parquet`。
6. 把每张图片的语义重复摘要写回 `parameter_table`。

## Artifact 与 Schema

### parameter_table

新增参数列：

```text
semantic_embedding_ref
semantic_duplicate_group_id
semantic_duplicate_count
semantic_duplicate_score
semantic_duplicate_nearest_image_id
```

`semantic_duplicate_score` 表示当前图片与 keeper 或最近重复候选的 cosine similarity。唯一图片可以为空。`semantic_duplicate_nearest_image_id` 表示与当前图片形成重复关系的 keeper 或最近图片。

### evaluation_table

新增算子输出列：

```text
semantic_duplicate_group_id
semantic_duplicate_count
semantic_duplicate_score
semantic_duplicate_nearest_image_id
semantic_duplicate_action
semantic_duplicate_reason
```

### embedding artifact

路径：

```text
artifacts/semantic_embeddings/
  embeddings.npy
  image_ids.parquet
  manifest.json
```

`manifest.json` 字段：

```text
artifact_schema_version
provider_name
provider_version
model_id
model_path
base_model
embedding_dimension
normalized
embedding_source
image_count
config_hash
```

### index artifact

路径：

```text
artifacts/semantic_index/
  faiss.index
  manifest.json
```

`manifest.json` 字段：

```text
artifact_schema_version
index_type
metric
threshold
source_embedding_ref
image_count
config_hash
```

第一版使用 cleaning run 内的本地 artifact 保存向量和索引，不接入向量数据库。后续如需跨 run 复用、长期检索或多数据集检索，可以新增 `SemanticIndexStore` 或 `VectorStoreEmbeddingIndex` 接口，但不属于本设计范围。

### relation table

新增 relation table：

```text
relations/semantic_duplicate_pairs.parquet
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

1. `relation_type` 使用 `semantic_duplicate`。
2. `source_image_id` 是 keeper。
3. `target_image_id` 是被命中的非 keeper。
4. `score` 是 cosine similarity。
5. `group_id` 使用稳定语义重复组 id。
6. `parameter_name` 使用 `semantic_duplicate_group_id`。
7. `computer_name` 使用 `semantic_duplicate_group_computer`。
8. `artifact_ref` 指向 `artifacts/semantic_index/faiss.index`。

## 评估逻辑

`duplicate.semantic_duplicate_check` 的 required parameters：

```text
semantic_duplicate_group_id
semantic_duplicate_count
semantic_duplicate_score
semantic_duplicate_nearest_image_id
```

evaluation columns：

```text
semantic_duplicate_group_id
semantic_duplicate_count
semantic_duplicate_score
semantic_duplicate_nearest_image_id
semantic_duplicate_action
semantic_duplicate_reason
```

评估规则：

1. `keep` 不是 `"first"` 时抛出明确错误。
2. `action` 不是 `"drop"` 或 `"review"` 时抛出明确错误。
3. 没有语义重复组，或者组数量为 1：输出 `keep`。
4. 每个语义重复组第一次出现的图片：输出 `keep`。
5. 同组后续图片：输出配置的 `action`，reason 包含 group id、score 和 nearest image id。

## 数据流

```text
BasicCleaner([{duplicate.semantic_duplicate_check: config}])
  -> CleaningRunPlanner
  -> SemanticEmbeddingComputer
       -> SemanticEmbeddingProvider
       -> artifacts/semantic_embeddings/*
       -> parameter_table.semantic_embedding_ref
  -> SemanticDuplicateGroupComputer
       -> read semantic embedding artifact
       -> build artifacts/semantic_index/faiss.index
       -> write relations/semantic_duplicate_pairs.parquet
       -> parameter_table.semantic_duplicate_*
  -> OperatorEvaluator
       -> evaluation_table.semantic_duplicate_*
       -> semantic_duplicate_action / semantic_duplicate_reason
  -> export / preview
```

## 错误处理

1. 未安装 semantic 可选依赖但使用默认 provider：抛出明确错误，提示安装语义可选依赖。
2. 外部 provider 返回维度不一致、空向量或非有限数值：抛出 `ValueError`。
3. 图片读取或解码失败：该图片 `semantic_embedding_ref=""`，不会参与语义分组。
4. Faiss 不可用且配置 `index="faiss_flat_ip"`：直接失败，不静默降级。
5. 默认模型下载失败且未配置 `model_path`：抛出明确错误，不静默替换模型。
6. `model_path` 指向的 ONNX 文件不存在或输出维度不是 384：抛出明确错误。
7. `action` 不在 `"drop"`、`"review"` 中：抛出明确错误。
8. `keep` 不是 `"first"`：抛出明确错误。
9. 没有任何有效 embedding：产出空分组，所有图片保持 `keep`。

## 测试策略

### Provider 层

1. 默认 `onnx_dinov2_small` provider 在安装 semantic 可选依赖后能返回 384 维 embedding。
2. 外部注入 provider 能被 `SemanticEmbeddingComputer` 调用。
3. 默认 provider 能通过 `model_path` 使用本地 ONNX 文件。
4. provider 返回维度不一致、NaN、Inf 或空向量时失败明确。

### Embedding artifact 层

1. `SemanticEmbeddingComputer` 写出 `embeddings.npy`、`image_ids.parquet` 和 `manifest.json`。
2. `parameter_table` 只写 `semantic_embedding_ref`，不保存向量本体。
3. 解码失败图片不写有效 embedding ref。

### Semantic duplicate 分组层

1. `SemanticDuplicateGroupComputer` 能读取 embedding artifact。
2. Faiss index artifact 被写出。
3. similarity `>= threshold` 的图片进入同组。
4. 非 keeper 产生 `relations/semantic_duplicate_pairs.parquet`。
5. 无有效 embedding 时不报错，所有图片保持唯一。

### Operator / e2e 层

1. 默认 registry 包含 `duplicate.semantic_duplicate_check`。
2. planner 能展开 `semantic_embedding_ref -> semantic_duplicate_*` 依赖。
3. evaluator 默认 `drop` 非 keeper，并支持 `action="review"`。
4. 集成测试运行 `BasicCleaner([{"duplicate.semantic_duplicate_check": {...}}])` 后，能看到 parameter、evaluation、relation 和 artifact 全部落盘。
5. Notebook 后续可基于 `preview_html` 按 `semantic_duplicate_group_id` 分组查看结果。

## 成功标准

1. `duplicate.semantic_duplicate_check` 能在 `BasicCleaner` 中作为正式逻辑算子使用。
2. 默认 `onnx_dinov2_small` image-image provider 可用，同时支持外部 provider 注入。
3. embedding 和 Faiss index 不进入宽表，只进入 run artifacts。
4. relation table 能解释 keeper、duplicate、score 和 index artifact 来源。
5. 默认命中后 `drop`，用户可配置为 `review`。
6. 第一版不引入向量数据库。
7. 不改变 pHash 算子、不改变现有 export 和 preview 语义。

## 后续扩展

1. 接入向量数据库，用于跨 run 复用、长期检索或多数据集检索。
2. 支持更复杂 keeper 策略，例如按图片质量、分辨率或业务字段选择代表图。
3. 支持批量增量索引和跨 run artifact 复用。
4. 支持语义聚类、离群检测和相似检索，但应新增独立逻辑算子或 feature 算子，不混入 `duplicate.semantic_duplicate_check`。
