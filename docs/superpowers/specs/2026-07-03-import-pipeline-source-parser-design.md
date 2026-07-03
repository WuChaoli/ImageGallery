# ImportPipeline Source Parser API 设计

## 背景

当前导入 API 需要用户先手动创建 reader，再把 `SourceRecord` 可迭代对象传给 pipeline：

```python
records = LocalDirectoryReader(source_dir).read()
result = ImportPipeline(storage=storage, output_dir=output_dir).run(records)
```

这个用法把 source 解析细节暴露给用户，也让 `ImportPipeline` 看起来不像一个完整导入任务。当前项目仍处于开发阶段，可以做破坏性 API 更新，优先得到清晰的一版主接口。

## 目标

1. `ImportPipeline` 初始化时直接接收输入 source。
2. 复杂输入由用户显式传入 parser 对象。
3. 简单本地路径支持快捷输入：`str | Path`。
4. `run()` 改为无参方法，不再接收 `Iterable[SourceRecord]`。
5. 第一版内置三类 parser：
   - `LocalPathParser`
   - `UrlPathParser`
   - `DatasetParser`
6. 同步迁移测试、example 和 notebooks 到新 API。

## 非目标

1. 不保留 `ImportPipeline(...).run(records)` 兼容路径。
2. 不支持 URL 字符串快捷输入。
3. 不实现 MinIO、S3 或其他对象存储作为 source reader。
4. 不新增 reference 或 copy_on_write 导入模式。
5. 不新增自动类型识别的大而全工厂。
6. 不迁移或兼容旧 notebook 的已执行输出内容。

## 新 API

### Parser 对象优先

推荐用法：

```python
result = ImportPipeline(
    source=LocalPathParser("/path/to/images"),
    storage=storage,
    output_dir=output_dir,
).run()
```

URL 清单：

```python
result = ImportPipeline(
    source=UrlPathParser("urls.txt", download_dir="downloads"),
    storage=storage,
    output_dir=output_dir,
).run()
```

已有 Dataset 文件：

```python
result = ImportPipeline(
    source=DatasetParser("source.parquet"),
    storage=storage,
    output_dir=output_dir,
).run()
```

### 本地路径快捷输入

简单本地路径可以直接传给 `source`：

```python
result = ImportPipeline(
    source="/path/to/images",
    storage=storage,
    output_dir=output_dir,
).run()
```

`str | Path` 快捷输入只表示本地路径。它不会被解释为 URL、dataset 文件或 URL 清单文件。

## 组件设计

### `SourceParser`

新增 parser 协议：

```python
class SourceParser(Protocol):
    def parse(self) -> list[SourceRecord]: ...
```

Parser 只负责把外部 source 解析为 `SourceRecord` 列表，不负责写 storage、不抽取图片 metadata、不生成 raw dataset。

### `LocalPathParser`

职责：

1. 接收本地文件或本地目录路径。
2. 如果 source 是目录，递归扫描支持的图片后缀。
3. 如果 source 是单个图片文件，生成一条 `SourceRecord`。
4. 保持目录扫描结果按路径排序，保证测试和 notebook 输出稳定。

路径规则：

1. 目录 source 的 `source_relative_path` 使用相对目录路径。
2. 单文件 source 的 `source_relative_path` 使用文件名。
3. `source_type` 使用 `local_path`。

错误：

1. 路径不存在时抛出 `FileNotFoundError`。
2. 文件后缀不支持时抛出 `ValueError`。

### `UrlPathParser`

职责：

1. 接收 URL 清单文件路径。
2. 每行一个 URL，空行跳过。
3. 复用当前 URL 安全边界：scheme、localhost/private IP、文件后缀、content-type、文件大小、文件魔数。
4. `download=True` 时下载到本地临时目录，并在 `SourceRecord.local_path` 写入下载文件路径。
5. `download=False` 时只生成外部来源记录，`local_path=None`。

命名说明：`UrlPathParser` 的 path 指 URL 清单文件路径，不表示单个 URL 字符串。

错误：

1. URL 清单文件不存在时抛出 `FileNotFoundError`。
2. URL 安全校验失败时抛出 `ValueError`。
3. 下载失败时抛出请求层异常。

这些 parser 级错误表示 source 配置或 source 清单不可解析，属于导入任务启动前错误，不写入 per-image `failure_manifest`。

### `DatasetParser`

职责：

1. 接收已有 dataset 文件路径。
2. 读取 `image_uri` 列生成 `SourceRecord`。
3. `source_uri` 缺失时回退为 `image_uri`。
4. 如果 `image_uri` 是本地绝对路径，则设置 `local_path`。

错误：

1. dataset 文件不存在时抛出 `FileNotFoundError`。
2. 缺少 `image_uri` 列时抛出 `ValueError`。

非本地或不可读的 `image_uri` 可以生成 `local_path=None`，后续 pipeline 在图片级处理阶段记录到 `failure_manifest`。

### `ImportPipeline`

新构造器：

```python
class ImportPipeline:
    def __init__(
        self,
        source: SourceParser | str | Path,
        storage: Storage,
        output_dir: str | Path,
        global_tags: Iterable[str] | None = None,
        max_shard_size: int = 10000,
    ) -> None:
        ...
```

规则：

1. `source` 是 parser 对象时，必须具备 `parse()` 方法。
2. `source` 是 `str | Path` 时，统一包装为 `LocalPathParser(source)`。
3. 其他类型抛出 `TypeError`。
4. `max_shard_size <= 0` 仍然抛出 `ValueError`。

新 `run()`：

```python
def run(self) -> ImportResult:
    records = self.source_parser.parse()
    ...
```

`run()` 不接受任何参数。调用 `run(records)` 应触发 Python 的普通 `TypeError`，作为破坏性 API 更新的直接反馈。

## 数据流

```text
用户 source
  -> ImportPipeline.__init__()
  -> SourceParser
  -> run()
  -> parse() 得到 SourceRecord 列表
  -> metadata extraction
  -> storage.write_bytes()
  -> raw.parquet
  -> import_report.json
  -> failure_manifest.jsonl
```

导入后的唯一图片主引用仍然是 `image_uri`。`source_uri` 只用于追溯和审计。

## 错误处理

1. source 无法解析时直接抛出异常，不生成导入产物。
2. parser 成功返回 records 后，单张图片的 metadata 或 storage 失败继续写入 `failure_manifest`。
3. `local_path is None` 的记录在 pipeline 图片级阶段失败，`error_stage` 为 `source`。
4. 空 source 返回空 records 时，pipeline 仍写出空 raw dataset、空 failure manifest 和 `0/0` report。

## 文件与导出

建议文件结构：

```text
src/image_gallery/importers/config.py
src/image_gallery/importers/local_path.py
src/image_gallery/importers/url_list.py
src/image_gallery/importers/dataset_file.py
src/image_gallery/importers/pipeline.py
src/image_gallery/importers/__init__.py
```

导出：

```python
__all__ = [
    "DatasetParser",
    "ImportPipeline",
    "ImportResult",
    "LocalPathParser",
    "SourceParser",
    "SourceRecord",
    "UrlPathParser",
]
```

旧类名 `LocalDirectoryReader`、`UrlListReader`、`DatasetFileReader` 不再作为公开导出保证。由于当前仍是开发阶段，可以同步修改所有本仓库引用。

## 测试计划

1. `LocalPathParser`：
   - 扫描本地目录中的支持图片。
   - 单文件图片生成一条记录。
   - 不存在路径抛出 `FileNotFoundError`。
   - 不支持后缀文件抛出 `ValueError`。
2. `UrlPathParser`：
   - 拒绝 localhost/private IP。
   - `download=False` 生成 `local_path=None` 的记录。
   - `download=True` 下载图片到 `download_dir`。
3. `DatasetParser`：
   - 读取 dataset 文件中的 `image_uri` 和 `source_uri`。
   - `source_uri` 缺失时回退为 `image_uri`。
   - 缺少 `image_uri` 列抛出 `ValueError`。
4. `ImportPipeline`：
   - `source=tmp_path` 快捷输入可导入目录。
   - `source=LocalPathParser(file_path)` 可导入单文件。
   - `source=DatasetParser(dataset_path)` 可导入 dataset 文件。
   - `source=UrlPathParser(url_list, download_dir)` 可导入下载后的 URL 图片。
   - `run(records)` 不再支持。
   - 非法 source 类型抛出 `TypeError`。
5. 同步更新 examples 和 notebooks 中的导入调用。

## 验收标准

1. `ImportPipeline(...).run()` 是唯一推荐调用方式。
2. `ImportPipeline(...).run(records)` 不再可用。
3. 本地目录、本地单文件、URL 清单和 Dataset 文件都可以通过 parser 进入导入流程。
4. 本地路径字符串快捷输入可以直接导入本地目录。
5. 现有 raw dataset、import report、failure manifest 产物语义不变。
6. 全量 `pytest`、`ruff` 和 `mypy` 通过。
