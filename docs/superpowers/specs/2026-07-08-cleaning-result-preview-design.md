# 清洗结果预览功能设计

## 背景

当前清洗平台已经能输出 `parameter_table.parquet`、`evaluation_table.parquet`、`relations/*.parquet`，并能通过 `export("clean")`、`export("dropped")` 生成 clean/drop 数据集。现有 `Cleaner.preview()` 主要返回统计摘要和少量行级样本，不适合人工检查图片清洗效果。

pHash 近重复算子带来了更明确的人工检查需求：用户希望查看 clean/drop 结果，尤其是按 `perceptual_duplicate_group_id` 分组查看 drop 数据集，确认 keeper 与被删除图片是否真的重复。

这个能力不应绑定在单个逻辑算子上。逻辑算子只负责产出可解释字段，预览功能应该作为清洗结果层面的通用观察工具。

## 目标

1. 在包内新增正式的清洗结果预览 API，而不是只放在 Notebook helper 中。
2. 第一版生成静态 HTML 文件，用户可以直接在浏览器中打开。
3. 支持按字段过滤、分组、排序和限制展示数量。
4. 支持 clean、drop、review、restricted 等 action 视图。
5. 支持图片缩略图展示，并能处理 MinIO-backed `s3://` 图片。
6. 为后续临时预览服务器预留接口边界，但第一版不实现服务器。

## 非目标

1. 第一版不实现交互式 Web 服务、分页接口、图片代理 endpoint 或长期运行的后台进程。
2. 第一版不实现每个逻辑算子的专属 preview renderer。
3. 第一版不支持 bbox、mask、embedding 降维图、CLIP 检索页等特殊可视化。
4. 第一版不做跨 run 缓存，也不持久化缩略图缓存索引。
5. 第一版不改变清洗执行、调度、export 和算子评估语义。

## 核心判断

preview 应该是 CleanResult 级别的通用能力，而不是 Operator 级别的定制能力。

算子职责：

```text
图片/数据 -> 参数字段 -> evaluation 字段 -> action/reason
```

preview 职责：

```text
清洗产物表 + 图片读取能力 -> 可读的预览视图
```

pHash 算子不需要实现自己的 preview。它只要产出以下字段，通用 preview 就可以通过 `groupby`、`sort_by`、`filters` 使用它们：

```text
perceptual_duplicate_group_id
perceptual_duplicate_count
perceptual_duplicate_distance
perceptual_duplicate_action
perceptual_duplicate_reason
```

只有当某类算子的解释形态无法用表格和图片网格表达时，才考虑后续扩展 renderer，例如检测框、分割 mask 或 embedding 可视化。

## 用户侧 API

第一版在 `Cleaner` 上新增 HTML 预览方法：

```python
cleaner.preview_html(
    "datasets/tests/operators_phash_duplicate/preview.html",
    action="drop",
    groupby="perceptual_duplicate_group_id",
    include_group_context=True,
    sort_by=["perceptual_duplicate_count", "perceptual_duplicate_distance"],
    columns_per_row=6,
)
```

建议签名：

```python
def preview_html(
    self,
    path: str,
    *,
    action: str | None = None,
    filters: dict[str, object] | None = None,
    groupby: str | None = None,
    include_group_context: bool = False,
    sort_by: list[str] | None = None,
    ascending: bool | list[bool] = True,
    caption_columns: list[str] | None = None,
    max_rows: int = 200,
    max_groups: int = 50,
    max_items_per_group: int = 20,
    thumbnail_size: int = 320,
    columns_per_row: int = 6,
) -> Path:
    """把当前清洗运行结果渲染为静态 HTML 预览页。"""
```

`action` 是 `filters={"final_action": action}` 的简写。若同时传入 `action` 和 `filters`，两者叠加生效。

`include_group_context` 只在设置 `groupby` 时生效。它表示先用 `action` 和 `filters` 找到命中行，再把这些命中行所在分组的其他行补回预览结果。这样 pHash drop 预览既可以以 drop 行为入口，又能看到同组 keeper。

## 包内模块

新增模块：

```text
src/image_gallery/cleaning/html_preview.py
```

第一版包含三类函数：

```python
@dataclass(frozen=True)
class PreviewHtmlOptions:
    """HTML 预览参数。"""


@dataclass(frozen=True)
class PreviewGroup:
    """一个预览分组。"""


def build_preview_frame(
    evaluation_table: pd.DataFrame,
    *,
    action: str | None = None,
    filters: dict[str, object] | None = None,
    groupby: str | None = None,
    include_group_context: bool = False,
    sort_by: list[str] | None = None,
    ascending: bool | list[bool] = True,
    max_rows: int = 200,
) -> pd.DataFrame:
    """按过滤和排序参数构造待预览行。"""


def build_preview_groups(
    frame: pd.DataFrame,
    *,
    groupby: str | None = None,
    max_groups: int = 50,
    max_items_per_group: int = 20,
) -> list[PreviewGroup]:
    """把待预览行转为分组结构。"""


def write_preview_html(
    frame: pd.DataFrame,
    path: str | Path,
    *,
    dataset: Dataset,
    options: PreviewHtmlOptions,
) -> Path:
    """渲染并写出静态 HTML。"""
```

`BasicCleaner.preview_html()` 负责从当前 run 中取 `tables.evaluation_table` 和 `context.dataset`，然后调用这些包内函数。

## 数据流

```text
BasicCleaner.run()
  -> CleaningTables.evaluation_table
  -> BasicCleaner.preview_html(...)
  -> build_preview_frame(..., include_group_context=...)
  -> build_preview_groups(...)
  -> render static HTML
  -> write preview.html
```

第一版只读 `evaluation_table`。因为当前 evaluator 已经把 pHash 分组参数复制到了 `evaluation_table`，所以 pHash drop group 预览不需要额外 join `parameter_table`。

后续若某些 preview 需要 relation table，可以新增可选参数或内部读取逻辑，但不作为第一版要求。

## HTML 展示

HTML 页面结构：

1. 顶部摘要：总行数、展示行数、过滤条件、分组字段、排序字段。
2. 若未设置 `groupby`：展示普通图片网格。
3. 若设置 `groupby`：按组展示，每组包含组名、组内数量和图片卡片。
4. 图片卡片包含缩略图和 caption 字段。
5. 图片读取失败时，卡片显示错误信息，不中断整个 HTML 生成。

为了支持 `s3://` 图片，第一版使用 base64 内嵌缩略图：

```text
Dataset.read_image(image_uri)
  -> Pillow resize thumbnail
  -> encode jpeg/png bytes
  -> data:image/...;base64,...
```

这样 HTML 文件脱离 Python 进程后仍可查看。代价是 HTML 文件会变大，因此通过 `max_rows`、`max_groups` 和 `max_items_per_group` 控制规模。

## pHash drop group 预览

pHash 算子的推荐调用方式：

```python
cleaner.preview_html(
    "datasets/tests/operators_phash_duplicate/preview.html",
    action="drop",
    groupby="perceptual_duplicate_group_id",
    include_group_context=True,
    sort_by=["perceptual_duplicate_count", "perceptual_duplicate_distance"],
    ascending=[False, True],
    columns_per_row=6,
)
```

这里 `include_group_context=True` 会把 drop 命中行所在分组的 keeper 一并补回。因此每组可以同时看到保留图和被删除图，但该能力仍然只依赖通用 `groupby` 字段，不需要 pHash 算子实现专属 preview。

后续如需更强的重复组语义，可以通过 relation table 扩展一个 preset：

```python
preview_preset="duplicate_groups"
```

该 preset 可以读取 `relations/perceptual_duplicate_pairs.parquet`，显式区分 keeper、duplicate 和 pair score。这个 preset 不属于第一版。

## 错误处理

1. `groupby` 字段不存在：抛出 `ValueError`。
2. `sort_by` 字段不存在：抛出 `ValueError`。
3. `filters` 字段不存在：抛出 `ValueError`。
4. `action` 不在已知 action 中：抛出 `ValueError`。
5. `include_group_context=True` 但未设置 `groupby`：抛出 `ValueError`。
6. 图片读取失败：写入错误卡片，不抛出整体异常。
7. `Cleaner` 尚未运行：沿用现有 `CleanerStateError`。

## 测试策略

1. 单元测试 `build_preview_frame`：
   - action 过滤生效。
   - filters 叠加生效。
   - `include_group_context=True` 时补回同组上下文行。
   - sort_by 和 ascending 生效。
   - 缺失字段抛出 `ValueError`。
2. 单元测试 `build_preview_groups`：
   - 无 groupby 时返回单个默认分组。
   - 有 groupby 时按字段分组。
   - `max_groups` 和 `max_items_per_group` 生效。
3. 单元测试 HTML renderer：
   - 写出 HTML 文件。
   - HTML 包含摘要、caption、图片 data URI 或错误卡片。
4. 集成测试 `BasicCleaner.preview_html`：
   - 最小清洗 run 后能写出 HTML。
   - drop 过滤能只展示 drop 行。

## 成功标准

1. 用户可以通过 `cleaner.preview_html(...)` 在包内生成正式 HTML 预览文件。
2. pHash drop 数据集可以按 `perceptual_duplicate_group_id` 分组查看，并可通过 `include_group_context=True` 同时查看 keeper。
3. clean/drop/review/restricted 都可通过通用过滤参数预览。
4. 第一版不需要每个逻辑算子实现独立 preview。
5. HTML 对 MinIO 图片可用，打开文件后不依赖 Jupyter 或临时服务器。
6. 相关单元测试和集成测试通过。

## 后续扩展

1. `serve_cleaning_preview(...)`：基于同一 preview query 增加临时 HTTP 服务。
2. relation-aware preset：显式展示 keeper、duplicate 和 pair score。
3. renderer 插件：支持 bbox、mask、embedding、CLIP 检索等特殊解释形态。
4. 缩略图缓存：避免大规模数据集重复生成 base64 缩略图。
