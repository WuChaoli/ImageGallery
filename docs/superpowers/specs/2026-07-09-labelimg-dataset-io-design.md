# LabelImg Dataset I/O Design

## 背景

ImageGallery 当前 Dataset 以 Parquet/CSV/JSONL 表格文件为主体，图片地址通过 `image_uri` 指向本地文件或远端 Storage。LabelImg 不能直接读取 Parquet，也不能访问 MinIO 等对象存储，因此需要一个面向 LabelImg 的本地导出与回收能力：

1. 把 Dataset 中的图片拉取到本地目录，方便 LabelImg 打开。
2. 在导出目录保留原始 Dataset 表格，方便标注完成后恢复行级上下文。
3. 如果 Dataset 已有 bbox 标注，导出为 LabelImg 默认支持的 Pascal VOC XML。
4. 标注完成后读取 XML，并把 bbox 以相对坐标写回 Dataset。

LabelImg 官方默认保存 Pascal VOC XML，也支持 YOLO TXT 和 CreateML JSON。第一版只支持 Pascal VOC XML，避免同时引入类别索引、YOLO 坐标语义和 CreateML JSON 结构。

## 目标

1. 将 Dataset I/O 统一为 `load/export` 模型。
2. 支持通过可插拔 loader/exporter 扩展不同外部格式。
3. 提供 LabelImg Pascal VOC 导出能力：本地图片、`raw.parquet`、同名 XML。
4. 提供 LabelImg Pascal VOC 回收能力：读取目录并生成带 `annotations` 列的 Dataset。
5. Dataset 内部 bbox 只保存相对坐标，不保存绝对像素坐标。
6. 保持当前 Dataset 一图一行结构，多框标注写入单个 `annotations` 列。

## 非目标

1. 第一版不支持 YOLO TXT、CreateML JSON、COCO 或 Label Studio。
2. 第一版不实现 LabelImg GUI 自动配置或启动。
3. 第一版不把标注拆成单独 annotation parquet。
4. 第一版不支持 polygon、mask、rotated box、keypoints 等非矩形框标注。
5. 第一版不做类别字典管理，只保留 XML 中的 label 字符串。

## API 设计

`Dataset.load(...)` 是所有外部资源进入 Dataset 的统一入口。普通表格文件由内置 loader 处理，LabelImg 目录由显式 loader 处理。

```python
dataset = Dataset.load("raw.parquet", storage=minio_storage)

labeled_dataset = Dataset.load(
    LabelImgLoader(input_dir="datasets/labelimg/task-001")
)
```

`Dataset.export(...)` 是 Dataset 输出到外部资源的统一出口。表格导出和 LabelImg 导出都通过 exporter 实现。

```python
dataset.export(
    TabularDatasetExporter(output_path="exports/clean.parquet")
)

dataset.export(
    LabelImgExporter(output_dir="datasets/labelimg/task-001")
)
```

破坏式 API 调整：

1. `Dataset.from_path(...)` 改为 `Dataset.load(...)`。
2. 旧 `Dataset.export(output_dataset_path, address_policy="keep")` 改为 `Dataset.export(TabularDatasetExporter(...))`。
3. `Dataset.write(...)` 保留，用于把内存 `DataFrame` 写成 Dataset 文件。

协议：

```python
class DatasetLoader(Protocol):
    def load(self) -> Dataset:
        ...


class DatasetExporter(Protocol):
    def export(self, dataset: Dataset) -> DatasetExportResult:
        ...
```

`Dataset.load(source, storage=None)` 支持两类输入：

1. `str | Path`：按文件后缀加载 Parquet/CSV/JSONL。
2. `DatasetLoader`：调用 loader 返回 Dataset。

`Dataset.export(exporter)` 只接收 `DatasetExporter`，避免继续扩大旧参数形态。

## 模块设计

新增模块：

```text
src/image_gallery/dataset/io.py
src/image_gallery/dataset/exporters.py
src/image_gallery/annotations/__init__.py
src/image_gallery/annotations/labelimg.py
```

职责：

1. `dataset/io.py` 定义 `DatasetLoader`、`DatasetExporter`、`DatasetExportResult`。
2. `dataset/exporters.py` 提供 `TabularDatasetExporter` 和表格读写辅助。
3. `annotations/labelimg.py` 提供 `LabelImgExporter`、`LabelImgLoader`、Pascal VOC XML 读写和坐标转换。
4. `Dataset` 只保留用户入口和通用数据读取能力，不直接承载 XML 细节。

## LabelImg 目录协议

导出目录结构：

```text
task-001/
  raw.parquet
  images/
    <image_id>.<ext>
  annotations/
    <image_id>.xml
```

约束：

1. 图片 basename 使用 `image_id`，避免源文件名重复、中文、空格或特殊字符导致冲突。
2. XML basename 必须与图片 basename 一致，这是 LabelImg 自动加载同名标注文件的关键。
3. `raw.parquet` 写在任务根目录，作为回收时恢复 Dataset 行上下文的事实来源。
4. `images/` 和 `annotations/` 分目录存放。LabelImg 支持独立 annotation 目录，但需要用户在 GUI 中手动设置。

LabelImg 操作顺序：

1. 点击 `Open Dir`，选择 `task-001/images/`。
2. 点击 `Change default saved annotation folder`，选择 `task-001/annotations/`。
3. 开始标注、检查或修正已有 XML。

这个顺序来自 LabelImg 行为约束：`Open Dir` 会把默认保存目录设为图片目录；如果使用独立 `annotations/`，用户必须显式切换保存目录。源码中打开图片时会优先从 `default_save_dir/<image_basename>.xml` 读取 Pascal VOC XML，因此分目录可用，但不能省略保存目录设置。

## LabelImgExporter

输入：

```python
LabelImgExporter(
    output_dir: str | Path,
    annotation_column: str = "annotations",
    dataset_filename: str = "raw.parquet",
    overwrite: bool = False,
)
```

输出：

1. `output_dir/raw.parquet`：原 Dataset 表格副本。导出时把 `image_uri` 保持为原始地址，不改写为本地图片路径。
2. `output_dir/images/<image_id>.<ext>`：通过 `Dataset.read_image_bytes()` 拉取出来的本地图片。
3. `output_dir/annotations/<image_id>.xml`：当 `annotations` 列存在且非空时生成。
4. `DatasetExportResult`：包含输出目录、图片数量、XML 数量和失败明细。

图片扩展名规则：

1. 优先使用 Dataset 的 `file_extension` 列。
2. 缺失时从 `source_file_name` 或 `image_uri` 后缀推导。
3. 仍无法推导时默认使用 `.jpg`，但仅在图片 bytes 可被 Pillow 识别且格式为 JPEG 时允许。

导出前置条件：

1. 必须存在 `image_id`、`image_uri`、`width`、`height`。
2. `image_id` 不能为空且导出批次内唯一。
3. `width`、`height` 必须为正数。
4. `output_dir` 已存在且 `overwrite=False` 时失败，避免覆盖人工标注成果。

## LabelImgLoader

输入：

```python
LabelImgLoader(
    input_dir: str | Path,
    annotation_column: str = "annotations",
    dataset_filename: str = "raw.parquet",
    output_filename: str = "labeled.parquet",
    strict: bool = True,
)
```

加载流程：

1. 读取 `input_dir/raw.parquet` 为基础 Dataset。
2. 扫描 `input_dir/annotations/*.xml`。
3. 用 XML basename 匹配 Dataset 的 `image_id`。
4. 解析 Pascal VOC XML 中的所有 `object/bndbox`。
5. 使用 Dataset 行内 `width`、`height` 把绝对坐标转换成相对坐标。
6. 写出带 `annotations` 列的 labeled parquet，并返回指向该文件的 Dataset。

第一版默认写出：

```text
task-001/labeled.parquet
```

`Dataset.load(LabelImgLoader(...))` 返回指向 `labeled.parquet` 的 Dataset。实现时命名使用 `Dataset.load(...)`，不保留 `from_path`。

严格模式：

1. `strict=True` 时，XML basename 找不到对应 `image_id` 直接失败。
2. XML 尺寸与 Dataset 尺寸不一致直接失败。
3. bbox 坐标越界或无效直接失败。
4. `strict=False` 可跳过无效 XML，并把失败明细写入 `labelimg_load_report.json`。

## annotations 列模型

Dataset 保持一图一行，`annotations` 列保存 list。每个 bbox 使用以下结构：

```python
{
    "label": "person",
    "bbox": {
        "x_min": 0.12,
        "y_min": 0.20,
        "x_max": 0.34,
        "y_max": 0.80,
    },
    "format": "relative_xyxy",
    "source": "labelimg_pascal_voc",
    "difficult": 0,
    "truncated": 0,
    "pose": "Unspecified",
}
```

坐标规则：

1. Dataset 内部只保存相对坐标，范围 `[0, 1]`。
2. `x_min`、`x_max` 以图片宽度归一化。
3. `y_min`、`y_max` 以图片高度归一化。
4. 必须满足 `x_min < x_max` 且 `y_min < y_max`。
5. 导出到 Pascal VOC XML 时转换为整数像素坐标。

Pascal VOC XML 写出字段：

1. `folder`：`images`。
2. `filename`：`<image_id>.<ext>`。
3. `path`：导出后的本地图片绝对路径。
4. `size/width`、`size/height`、`size/depth`：来自 Dataset 和 Pillow 读取结果。
5. `object/name`：`annotation["label"]`。
6. `object/pose`：缺省为 `Unspecified`。
7. `object/truncated`：缺省为 `0`。
8. `object/difficult`：缺省为 `0`。
9. `object/bndbox`：绝对像素 `xmin/ymin/xmax/ymax`。

## 错误处理

用户可理解错误：

1. `missing required columns: image_id, image_uri, width, height`
2. `duplicate image_id in dataset export: <image_id>`
3. `cannot read image bytes for image_id=<image_id>: <reason>`
4. `annotation xml has no matching image_id: <xml_path>`
5. `annotation size mismatch for image_id=<image_id>: dataset=(w,h), xml=(w,h)`
6. `invalid bbox for image_id=<image_id>, label=<label>: <bbox>`

第一版不做部分成功的隐式 Dataset 写回。严格模式默认失败优先，用户需要看到真实问题。

## 测试策略

单元测试：

1. `Dataset.load("raw.parquet")` 能加载表格 Dataset。
2. `Dataset.load(loader)` 能委托 loader。
3. `dataset.export(TabularDatasetExporter(...))` 能写出表格并去掉 `source_uri`。
4. `LabelImgExporter` 能导出图片、`raw.parquet` 和 Pascal VOC XML。
5. `LabelImgLoader` 能从 Pascal VOC XML 回收相对 bbox。
6. 坐标转换覆盖边界值和非法框。
7. 分目录协议下，图片 basename 与 XML basename 保持一致。

集成测试：

1. 使用本地临时图片构造 Dataset，导出为 LabelImg 目录，再加载回带 `annotations` 的 Dataset。
2. 使用 storage-backed Dataset 的 `read_image_bytes()` 路径验证远端图片导出不需要额外下载实现。

不在第一版测试中启动 LabelImg GUI。GUI 行为只通过目录协议和 Pascal VOC XML 结构保证兼容。

## 迁移影响

需要同步更新现有调用：

1. `Dataset.from_path(path)` 改为 `Dataset.load(path)`。
2. `Dataset.export(output_path)` 改为 `Dataset.export(TabularDatasetExporter(output_path))`。
3. Notebook 和测试中的旧 API 全量替换，不保留兼容层。

因为项目仍处于开发阶段，本次设计允许破坏式重构，目标是让 Dataset I/O API 一次性转向可扩展形态。
