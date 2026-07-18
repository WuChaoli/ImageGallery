# Test Dataset Strategy

## Purpose

定义仓库默认测试样本、真实数据验收与测试命令分层的当前承诺，确保普通 CI 快速、确定且不依赖外部服务，同时保留显式真实数据验收入口。

## Requirements

### Requirement: 固定本地小样本数据集

系统 SHALL 在仓库内提供从 `sample_1000` 使用 `random_state=20260706` 一次性抽取的 10 张固定测试图片及对应 Parquet。默认测试运行期间 MUST NOT 重新随机抽样。

#### Scenario: 小样本内容固定
- **WHEN** 加载默认测试数据集
- **THEN** 数据集 SHALL 恰好包含 10 条记录，且重复运行得到相同的 image_id 集合和 dataset fingerprint

#### Scenario: 图片全部位于本地
- **WHEN** 遍历默认测试数据集的 image_uri
- **THEN** 每个 URI SHALL 解析为当前 checkout 内 `tests/fixtures/sample_10/images/` 下可读取的本地文件

#### Scenario: 默认测试禁用网络
- **WHEN** 使用 pytest socket 隔离运行默认测试
- **THEN** 小样本加载和清洗 SHALL 成功且 MUST NOT 创建 MinIO 连接

### Requirement: 测试数据路径可移植

fixture Parquet MUST NOT 固化生成机器的绝对路径。测试装配层 SHALL 根据当前 checkout 解析图片位置并提供绝对本地 `file://` URI。

#### Scenario: 从不同工作目录运行
- **WHEN** 从仓库根目录以外的工作目录加载测试 fixture
- **THEN** 10 张图片 SHALL 仍能被 Dataset 正确读取

#### Scenario: 检查提交内容
- **WHEN** 检查 fixture Parquet 中的持久化图片引用
- **THEN** 引用 MUST NOT 包含生成机器的盘符、用户目录或 MinIO URI

### Requirement: 默认测试与真实数据验收分层

系统 SHALL 将依赖 `sample_1000` 或 MinIO 的测试同时标记为 `slow` 和 `real_dataset`，将依赖 PostgreSQL、pgvector、PyIceberg 或 S3-compatible 容器的测试标记为 `dataset_backend`。Python CI 默认 `test` 任务 SHALL 排除 `slow` 与 `dataset_backend` 测试，`test-all` SHALL 排除 `dataset_backend` 测试。PR 涉及 MinIO、sample_1000 或真实数据时 MUST 额外运行 `test-real`；涉及 slow、并发、缓存、状态恢复或资源生命周期时 MUST 额外运行 `test-all`；涉及 DatasetManager Backend 时 MUST 额外运行 `dataset-backend`。

#### Scenario: 运行默认测试
- **WHEN** 执行 `uv run python -m tools.ci test`
- **THEN** pytest SHALL 不收集 slow 测试，且清洗集成测试 SHALL 使用本地 sample_10

#### Scenario: 运行真实数据验收
- **WHEN** 变更涉及真实数据并执行 `uv run python -m tools.ci test-real`
- **THEN** pytest SHALL 仅运行 `real_dataset` 测试，并允许在 MinIO 或 sample_1000 不可用时明确跳过

#### Scenario: 运行完整测试
- **WHEN** 高风险运行时变更执行 `uv run python -m tools.ci test-all`
- **THEN** pytest SHALL 同时收集默认测试和真实数据测试，但 SHALL NOT 启动 `dataset_backend` 容器测试

#### Scenario: 运行 DatasetManager Backend 验收
- **WHEN** Backend 相关变更执行 `uv run python -m tools.ci dataset-backend`
- **THEN** pytest SHALL 仅运行 DatasetManager 的 `dataset_backend` 容器集成测试

### Requirement: 边界行为独立于随机样本内容

完全重复、近似重复、空白、异常尺寸等需要精确输出的测试 MUST 使用专用确定性输入，不得假定随机抽取的 10 张图片包含特定边界案例。

#### Scenario: 验证重复检测
- **WHEN** 测试完全重复或近似重复算子的分组和 action
- **THEN** 测试 SHALL 使用明确构造的重复图片集合并断言确定结果
