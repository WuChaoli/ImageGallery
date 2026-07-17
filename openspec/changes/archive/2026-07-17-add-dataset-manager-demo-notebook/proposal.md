## Why

DatasetManager 已具备真实 PostgreSQL/pgvector、PyIceberg 与 MinIO 生命周期能力，但目前只有测试代码，没有一条面向用户、可阅读且可重复执行的完整演示。需要提供随仓库交付的真实图片材料和单 Notebook 双环境入口，让用户既能连接已有服务，也能显式创建隔离演示服务。

## What Changes

- 在 `examples/dataset_manager_demo/` 提供一个全中文 DatasetManager 生命周期 Notebook、配套 README、环境示例和共享 helper。
- 从现有 MinIO `sample_1000` 使用固定随机种子抽取 20 张图片，提交本地原图和可追溯 manifest。
- Notebook 自动探测 `.env`：配置完整且可连接时默认复用已有 PostgreSQL/pgvector 与 MinIO；缺失或失败时给出中文诊断和修改指导。
- 提供用户显式执行的 demo Backend 创建、重建和清理命令，只管理带固定 demo 标识的 PostgreSQL/pgvector、MinIO 容器与 volume，并写入独立 `.env.demo`。
- 演示导入、托管存储、读取、Tag、Data+Vector commit、Checkpoint、Branch 分叉、版本迭代、回退、Clone、关闭重连和持久状态验证。
- 当前正式 Importer 尚未切换时，在 examples 内提供隔离的演示 adapter；后续仅替换 adapter，不改变 Notebook 主流程。
- 增加材料完整性、环境选择、安全边界和 Notebook 从头执行的自动化验证。

## Capabilities

### New Capabilities

- `dataset-manager-demo`: 定义 DatasetManager 演示材料、后端自动探测与显式重建、完整生命周期 Notebook 及可重复执行要求。

### Modified Capabilities

无。

## Impact

- 新增 `examples/dataset_manager_demo/` 下的 Notebook、helper、README、环境模板、20 张图片和 manifest。
- 可能增加仅供演示环境编排与 Notebook 自动执行所需的开发依赖或测试入口，不改变生产 DatasetManager、StorageManager 或正式 Importer 公共 API。
- 演示连接真实 PostgreSQL/pgvector、PyIceberg Warehouse 和 MinIO；容器模式要求本机 Docker 可用。
- Git 仓库体积会增加 20 张真实图片的大小，素材来源和内容哈希由 manifest 固定。
