# `dataset_manager/` 模块指南

## 职责

- 管理 Backend、DatasetRepo、每 Dataset 单 Iceberg Table、Branch、Checkpoint、回退与同 Repo 状态 Clone。
- 管理 Repo 级 Tag Definition、VectorField、pgvector 当前值和 durable operation recovery。
- 不负责图片 bytes 存储、向量生成、搜索、复杂历史合并、删除、retention 或 GC。

## 当前能力

- 提供 SQLite/PyIceberg 本地 Backend 和 PostgreSQL/PyIceberg SqlCatalog 真实 Backend。
- 以不可变 Repo ID、独立 Iceberg Namespace 和显式 DatasetView 基线隔离状态并处理乐观并发。
- 支持 Dataset 与调用方提供向量的组合原子发布及关键故障点幂等恢复。
- VectorField 当前只接受 `float32`，距离度量限制为 `cosine`、`dot` 或 `l2`，创建后空间契约不可修改。

## 公共入口

- 从 `image_gallery.dataset_manager` 导入 `DatasetManager`、领域 handle、DTO 和稳定异常。
- Dataset 局部操作由 `DatasetRepo`、`Dataset`、`DatasetView` 与 `VectorField` 承担，不下沉到 `DatasetManager`。

## 核心契约与边界

- Iceberg 保存 Dataset Schema、行、Tag Assignment 和历史；PostgreSQL 保存控制面与 Repo 当前向量。
- 图片读取必须委托 `image_gallery.storage_manager`，行内位置只由 `storage_prefix_id + relative_path` 构成。
- 新平台不继承或隐式转换旧 `image_gallery.dataset` / `image_gallery.storage` 类型。
- `DatasetManager.local()` / `postgres()` 拥有其创建的 Engine；使用 context manager 或 `close()` 释放连接池。

## 开发与验证

- 单元测试：`uv run pytest tests/unit/dataset_manager`
- 真实 Backend：`uv run pytest -m dataset_backend tests/integration/dataset_manager`

## 相关文档

- 当前产品行为：`openspec/specs/dataset-repositories/`、`openspec/specs/iceberg-datasets/`、`openspec/specs/dataset-versioning/`、`openspec/specs/repository-tags/`、`openspec/specs/repository-vectors/`
- 面向用户的用法：根目录 `README.md`
