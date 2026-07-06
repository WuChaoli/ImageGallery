# Notebooks

This directory will contain Jupyter validation flows for each development stage.

Stage 0 only keeps the directory entrypoint. Business validation notebooks start after Stage 1.

- `cleaning_v3_builtin_test.ipynb`: 自包含验证 V3 清洗平台和第一批基础算子，不依赖 MinIO 或 importer 产物。
- `operators_builtin_test.ipynb`: 基于 importer 产物和可选 MinIO 环境验证内置算子流程。
