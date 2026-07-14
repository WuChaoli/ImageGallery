## 1. 固定本地测试数据集

- [ ] 1.1 先添加 sample_10 helper 契约测试，覆盖固定 10 条、稳定 image_id/fingerprint、本地可读 URI、跨工作目录加载和无 MinIO 连接
- [ ] 1.2 使用 `random_state=20260706` 从当前 sample_1000 抽样，复制 10 张图片并生成不含绝对路径的 `tests/fixtures/sample_10/raw.parquet`
- [ ] 1.3 实现测试专用 sample_10 loader，在临时目录中把 fixture 相对引用解析为当前 checkout 的绝对 `file://` URI
- [ ] 1.4 运行 sample_10 helper 测试并检查 fixture 未包含盘符、用户目录、S3/MinIO URI或衍生产物

## 2. 清洗集成测试迁移

- [ ] 2.1 先修改清洗集成测试，使默认真实执行路径期望 sample_10 且在 fixture loader 尚未接入时失败
- [ ] 2.2 将 StateGraph、TOML recipe 和 first-batch 清洗集成路径迁移到本地 sample_10，并将数量断言从 1000 改为 fixture 契约值
- [ ] 2.3 保留重复检测、空白和异常质量等专用确定性输入测试，不对随机 sample_10 的类别分布增加假设
- [ ] 2.4 将仍依赖 sample_1000/MinIO 的规模与真实存储验收集中到独立测试路径，并添加 `slow`、`real_dataset` 标记

## 3. pytest 与命令分层

- [ ] 3.1 先添加测试配置断言，验证 marker 已注册、默认命令排除 slow、真实验收命令仅选择 real_dataset
- [ ] 3.2 在 pytest 配置中注册 `slow` 和 `real_dataset` marker，并配置默认排除 slow 测试
- [ ] 3.3 更新 Makefile，提供默认测试、真实数据验收和包含 slow 的完整测试目标及直接 `uv run` 等价语义
- [ ] 3.4 更新根 AGENTS.md 的测试命令与数据集分层说明，确保与 OpenSpec 和 Makefile 一致

## 4. 验证

- [ ] 4.1 在 socket 禁用条件下运行 sample_10 helper 与迁移后的清洗集成测试，确认不访问 MinIO
- [ ] 4.2 使用 `--collect-only` 分别验证默认、real_dataset 和完整测试的收集边界
- [ ] 4.3 运行默认 pytest 并记录与改造前约 404 秒串行基线的耗时对比
- [ ] 4.4 显式运行 real_dataset 验收；环境不可用时确认测试以明确原因 skip，而不是失败
- [ ] 4.5 运行受影响文件的 ruff 与 pyright 检查，并确认没有改动生产 API
