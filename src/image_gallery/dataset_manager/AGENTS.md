# `dataset_manager/` 模块指南

## 职责

- 管理 Backend、DatasetRepo、每 Dataset 单 Iceberg Table、Branch、Checkpoint、回退，以及同 Repo 状态 Clone 和固定 View 物化。
- 管理 Repo 级 Tag Definition、强绑定模型的 VectorField、Dataset 范围向量生成、pgvector 当前值和 durable operation recovery。
- 不负责图片 bytes 存储、全 Repo 向量调度、搜索、复杂历史合并、删除、retention 或 GC。
- `manager.py` 负责 Backend 生命周期与跨组件领域编排；`_dataset_history.py` 集中 Dataset 历史、候选 Snapshot 发布和 durable recovery。
- `_tag_store.py` 与 `_vector_store.py` 分别管理 Repo Tag Definition、VectorField 定义和 Repo 当前向量；pending vectors 仍属于历史协议。
- `_schema_lock.py` 隔离 Repo Schema 修改锁；`_view_io.py` 组合固定 Snapshot 物理行与显式 Repo 当前向量；`_embedding.py` 执行已固定 Dataset 范围的可信批量推理和原子发布。

## 当前能力

- 提供 SQLite/PyIceberg 本地 Backend 和 PostgreSQL/PyIceberg SqlCatalog 真实 Backend。
- 以不可变 Repo ID、独立 Iceberg Namespace 和显式 DatasetView 基线隔离状态并处理乐观并发。
- Dataset Commit 默认以 replace 发布 Branch 完整状态，upsert 和 patch 必须显式选择；Schema additions、候选 Snapshot、Branch Head 和可选 Checkpoint 共用可恢复 operation。
- Dataset Schema 以递归 typed DTO 表达标量、List 和 Struct；只允许新增顶层可选业务列，已创建嵌套结构不可变更。
- `DatasetView` 以 DataFrame/Series 返回固定 Snapshot 的物理列与显式选择的 Repo 当前向量，并通过公开 owner 导航返回所属 Dataset/Repo。
- Branch 可从同 Dataset 的任意有效固定 View 创建，不隐式创建 Checkpoint；固定 View 物化为新 Dataset 时保留图片位置与内容身份，不继承历史或向量。
- `Dataset.generate_embed()` 默认固定 main 当前 Head，也可固定指定 Branch 或当前 Dataset 的精确 View；不推进 Iceberg 历史。
- VectorField 强绑定持久化模型定义，当前只接受 `float32`，距离度量限制为 `cosine`、`dot` 或 `l2`。
- 普通列与 VectorField 使用 `strip().casefold()` 统一判重；同 Repo Schema 修改串行，不同 Repo 保持独立锁域。

## 公共入口

- 从 `image_gallery.dataset_manager` 导入 `DatasetManager`、领域 handle、DTO 和稳定异常。
- Schema 通过 `repo.schema` 与 `dataset.schema` 修改；Dataset Commit 只接受普通字段 DataFrame，向量只能由 `Dataset.generate_embed()` 生成。需要新 Dataset 隔离时使用 `DatasetRepo.materialize_dataset()`，不要在消费者中编排 create/add/commit/checkpoint 多步写入。

## 核心契约与边界

- Iceberg 保存 Dataset Schema、行、Tag Assignment 和历史；PostgreSQL 保存控制面与 Repo 当前向量。
- Replace 只改变新 Branch Head 的行集合，不删除旧 Snapshot、Checkpoint、Tag Definition、历史 Tag Assignment、StorageManager bytes 或 Repo 当前向量。
- 同 Dataset 历史修改与 recovery 共用 history lock；需要 Schema lock 时始终先取 Repo Schema lock、再取 Dataset history lock。物化名称在 Catalog 副作用前 durable 预留。
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
