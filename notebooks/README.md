# Notebooks

This directory will contain Jupyter validation flows for each development stage.

Stage 0 only keeps the directory entrypoint. Business validation notebooks start after Stage 1.

- `_helpers/`: Notebook 与轻量测试脚本共享的初始化 helper，包括路径、MinIO storage、sample_1000 dataset 和清洗 v3 第一批算子配置。
- `cleaning_v3_sample_1000_test.ipynb`: 基于 default MinIO sample_1000 raw dataset 的清洗 v3 第一批算子分析型验证入口。
- `cleaning_v3_builtin_test.ipynb`: 自包含验证 V3 清洗平台第一批内置算子，包括质量、空白图和完全重复检查，不依赖 MinIO 或 importer 产物。
- `operators_builtin_test.ipynb`: 基于 importer 产物和可选 MinIO 环境验证内置算子流程。
