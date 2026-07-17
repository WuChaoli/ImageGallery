# `dataset_manager/` 模块指南

## 职责

- 管理 Backend、DatasetRepo、每 Dataset 单 Iceberg Table、Branch、Checkpoint、回退与同 Repo 状态 Clone。
- 管理 Repo 级 Tag Definition、强绑定模型的 VectorField、Dataset 范围向量生成、pgvector 当前值和 durable operation recovery。
- 不负责图片 bytes 存储、全 Repo 向量调度、搜索、复杂历史合并、删除、retention 或 GC。

## 当前能力

- 提供 SQLite/PyIceberg 本地 Backend 和 PostgreSQL/PyIceberg SqlCatalog 真实 Backend。
- 以不可变 Repo ID、独立 Iceberg Namespace 和显式 DatasetView 基线隔离状态并处理乐观并发。
- `DatasetView` 以 DataFrame/Series 返回物理列与显式选择的 Repo 当前向量；未选择时不隐式加载向量。
- `Dataset.generate_embed()` 默认固定 main 当前 Head，也可固定指定 Branch 或当前 Dataset 的精确 View；不推进 Iceberg 历史。
- VectorField 强绑定持久化模型定义，当前只接受 `float32`，距离度量限制为 `cosine`、`dot` 或 `l2`。
- 普通列与 VectorField 使用 `strip().casefold()` 统一判重；同 Repo Schema 修改串行，不同 Repo 保持独立锁域。

## 公共入口

- 从 `image_gallery.dataset_manager` 导入 `DatasetManager`、领域 handle、DTO 和稳定异常。
- Schema 通过 `repo.schema` 与 `dataset.schema` 修改；Dataset Commit 只接受普通字段 DataFrame，向量只能由 `Dataset.generate_embed()` 生成。

## 核心契约与边界

- Iceberg 保存 Dataset Schema、行、Tag Assignment 和历史；PostgreSQL 保存控制面与 Repo 当前向量。
- 图片读取必须委托 `image_gallery.storage_manager`，行内位置只由 `storage_prefix_id + relative_path` 构成；Prefix 冻结定义和模型定义持久化在 control schema，运行时资源不持久化。
- 新平台不继承或隐式转换旧 `image_gallery.dataset` / `image_gallery.storage` 类型。
- `DatasetManager.local()` / `postgres()` 拥有其创建的 Engine；DatasetManager 只关闭内部创建的 ModelManager，外部注入实例由调用方关闭。
- 当前 PostgreSQL 初始化自动执行 migration，连接默认具备创建 schema、extension 和 role 的管理员权限。

## 开发与验证

- 单元测试：`uv run pytest tests/unit/dataset_manager`
- 真实 Backend：`uv run pytest -m dataset_backend tests/integration/dataset_manager`

## 相关文档

- 当前产品行为：`openspec/specs/dataset-repositories/`、`openspec/specs/iceberg-datasets/`、`openspec/specs/dataset-versioning/`、`openspec/specs/repository-tags/`、`openspec/specs/repository-vectors/`
- 面向用户的用法：根目录 `README.md`
