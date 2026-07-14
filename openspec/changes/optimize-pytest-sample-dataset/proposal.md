## Why

当前默认 pytest 套件会多次对 MinIO `sample_1000` 执行真实图片清洗，三条路径约占串行测试总耗时的 90%，并使日常测试依赖外部存储。需要建立可复现的本地小样本测试层，同时保留 1000 张真实数据的显式验收能力。

## What Changes

- 从现有 `sample_1000` 使用固定随机种子一次性抽取 10 张图片，固化为仓库内本地测试数据集。
- 默认集成测试改用本地 `sample_10`，不得连接 MinIO，且所有 `image_uri` 指向可读取的本地图片。
- 重复检测及其他特定边界行为继续使用测试内的专用构造数据，不依赖随机样本恰好包含边界案例。
- 将 `sample_1000` 真实数据验收标记为 `slow` 和 `real_dataset`，从默认测试命令中排除。
- 提供独立命令运行真实数据验收，并保留全量执行入口。

## Capabilities

### New Capabilities
- `test-dataset-strategy`: 定义固定本地小样本、真实数据慢速验收、pytest marker 和测试命令的分层策略。

### Modified Capabilities
- `development-guidelines`: 默认测试命令改为排除慢速真实数据验收，并提供对应的直接 `uv run` 命令。

## Impact

- 影响 `tests/fixtures/`、清洗集成测试、测试数据 helper、pytest 配置和 Makefile 测试入口。
- 仓库新增 10 张本地测试图片及对应 Parquet，默认测试不再要求 MinIO 可用。
- 不修改生产 API、清洗运行时行为或 Notebook 对 `sample_1000` 的人工验收方式。
