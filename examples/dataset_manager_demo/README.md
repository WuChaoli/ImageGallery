# DatasetManager 中文演示

[`dataset_manager_demo.ipynb`](dataset_manager_demo.ipynb) 使用真实 PostgreSQL/pgvector、PyIceberg SqlCatalog 和 MinIO，连续演示图片导入、存储、读取、Tag、commit、Branch、Checkpoint、模型托管向量生成、回退、Clone 和重连。

向量章节展示冻结模型定义与 VectorField 强绑定、默认 main Head 生成、普通列和向量列的统一 DataFrame 读取、增量跳过、覆盖生成、指定 View 范围，以及关闭重连后的恢复。向量是按 `asset_id` 复用的 Repo 当前值；生成向量不会创建或移动 Dataset 的 Iceberg Snapshot。

## 准备环境

Notebook 会自动查找 `.env`。复制 [`.env.example`](.env.example) 并填写已有服务配置；探测只有在 PostgreSQL、pgvector、Warehouse 和 MinIO 全部可用时才通过。失败只会显示诊断，不会自动启动容器或修改 `.env`。

没有已有服务时，需要本机 Docker 可用，然后在 Notebook 中显式运行：

```python
demo_backend = start_demo_backend(demo_root=DEMO_ROOT / "runtime", recreate=True)
```

临时连接信息只保存在 `DemoBackendSession.config` 内存中，不会把数据库或 MinIO 凭证写入磁盘。结束时显式运行 `stop_demo_backend(...)`；该函数拒绝操作 existing session。

## 演示材料

`materials/raw_images/` 包含从现有 MinIO `sample_1000` 以 seed `20260717` 固定抽取的 20 张图片。`sample_manifest.json` 保存来源 URI、本地路径、大小和 SHA-256；Notebook 运行不需要连接源数据集。

## 临时 Importer 边界

正式 Importer 尚未切换到 DatasetManager，本目录的 `DemoDatasetImporter` 只是演示 adapter，不从 `image_gallery` 导出且不会进入 wheel。未来切换正式 Importer 时只替换 adapter，Notebook 生命周期保持不变。
