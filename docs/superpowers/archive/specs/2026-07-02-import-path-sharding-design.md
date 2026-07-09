# 导入图片受管路径分片设计

## 背景

当前 `ImportPipeline` 将图片写入：

```text
images/raw/<image_id>/<source_file_name>
```

这种路径会在受管 storage 中暴露原始文件名。导入后的图片应使用 UUID 重命名，同时保留原始扩展名，并按日期和 shard 分布，避免单个目录内图片数量过大。

## 目标

1. 导入图片写入受管 storage 时，不再使用原始文件名作为受管文件名。
2. 受管文件名使用 `image_id` 对应 UUID，并保留原始扩展名。
3. 图片按导入日期和 shard 分布：

```text
images/raw/<yyyy-mm-dd>/shard_001/<uuid>.<ext>
```

4. 默认每个 shard 最多保存 10000 张成功导入图片。
5. `source_file_name` 继续保留原始文件名，用于追溯。

## 非目标

1. 不新增 raw Dataset schema 字段。
2. 不新增 `object_path` 字段。
3. 不引入可插拔 path policy 抽象。
4. 不改变 `image_id`、`source_uri`、`image_uri`、`source_file_name` 的语义。
5. 不迁移已经导入到旧路径的历史图片。

## 路径规则

`ImportPipeline` 生成 object path 时使用以下格式：

```text
images/raw/<import_date>/shard_<index>/<image_id><extension>
```

示例：

```text
images/raw/2026-07-02/shard_001/550e8400-e29b-41d4-a716-446655440000.jpg
```

规则细节：

1. `import_date` 使用本地运行日期，格式为 `yyyy-mm-dd`。
2. `shard_<index>` 从 `shard_001` 开始，至少三位补零。
3. shard 只按成功导入图片计数；失败图片不占 shard 位置。
4. 默认 `max_shard_size` 为 `10000`。
5. `extension` 来自 `source_file_name` 的后缀，并统一转小写。
6. 若 `source_file_name` 没有扩展名，则使用空扩展名，不额外推断格式。

## 组件变更

### ImportPipeline

`ImportPipeline.__init__()` 新增参数：

```python
max_shard_size: int = 10000
```

参数校验：

1. `max_shard_size` 必须大于 0。
2. 非法值抛出 `ValueError`。

`run()` 中每次成功写入前，根据当前成功行数计算 shard：

```text
success_index = len(imported_rows)
shard_index = success_index // max_shard_size + 1
```

然后构造 object path 并写入 storage。

### 私有辅助函数

新增私有函数负责路径拼接，保持 `run()` 主流程可读：

```python
_build_raw_object_path(import_date, shard_index, image_id, source_file_name) -> str
```

该函数只负责提取后缀、格式化 shard 和拼接路径。

## 数据流

1. Source Reader 输出 `SourceRecord`，其中 `source_file_name` 仍是原始文件名。
2. Pipeline 抽取 metadata。
3. Pipeline 生成 UUID `image_id`。
4. Pipeline 根据本地日期、成功导入计数和 `max_shard_size` 生成受管 object path。
5. Storage 写入 `images/raw/<date>/shard_xxx/<uuid>.<ext>`。
6. Storage 返回 `image_uri`，raw Dataset 写入该 `image_uri`。
7. raw Dataset 继续保存 `source_file_name` 作为原始文件名追溯字段。

## 错误处理

1. `max_shard_size <= 0` 在初始化时失败，抛出 `ValueError`。
2. 单张图片 metadata 或 storage 写入失败时，仍进入 `failure_manifest`，不阻断整批导入。
3. 失败图片不占 shard 计数，避免 shard 中出现未写入图片造成的计数空洞。

## 测试计划

1. 更新 pipeline 测试，断言 `image_uri` 不包含原始文件名。
2. 断言 `image_uri` 包含 `images/raw/<today>/shard_001/`。
3. 断言文件名是 UUID 加小写原始扩展名，例如 `<uuid>.jpg`。
4. 使用 `max_shard_size=1` 导入两张有效图片，验证第二张进入 `shard_002`。
5. 保留现有失败样本测试，确认失败图片不影响成功样本路径。
6. 重新运行 Notebook 导入测试，确认新库中生成日期/shard/uuid.ext 路径。

## 验收标准

1. 新导入图片的 `image_uri` 不暴露原始文件名。
2. raw Dataset 中 `source_file_name` 仍保留原始文件名。
3. 默认每个 shard 最多 10000 张成功导入图片。
4. 可通过 `ImportPipeline(max_shard_size=...)` 在测试或特殊场景中调整 shard 大小。
5. 阶段 2 其他导入产物 `import_report` 和 `failure_manifest` 行为不变。
