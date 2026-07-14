# semantic-duplicate-operator Specification

## Purpose
TBD - created by archiving change complete-superpowers-gaps. Update Purpose after archive.
## Requirements
### Requirement: 语义去重算子
系统 SHALL 提供 `duplicate.semantic_duplicate_check` 逻辑算子，基于深度学习 embedding 检测语义相似的图片对。

#### Scenario: 算子注册
- **WHEN** 使用 `create_default_registry()` 创建算子注册表
- **THEN** 注册表 SHALL 包含 `duplicate.semantic_duplicate_check` 逻辑算子

#### Scenario: 算子配置
- **WHEN** 配置语义去重算子
- **THEN** 支持参数：`threshold=0.92`（相似度阈值）、`keep="first"`（保留策略）、`action="drop"`、`batch_size=32`

#### Scenario: 评估列输出
- **WHEN** 算子评估完成
- **THEN** parameter_table SHALL 包含 `semantic_embedding_ref`、`semantic_duplicate_group_id`、`semantic_duplicate_count`、`semantic_duplicate_score`、`semantic_duplicate_nearest_image_id` 列；evaluation 表 SHALL 追加 `semantic_duplicate_action` 和 `semantic_duplicate_reason` 列

### Requirement: SemanticEmbeddingProvider 协议
系统 SHALL 定义 `SemanticEmbeddingProvider` 可插拔协议，支持替换 embedding 后端。

#### Scenario: Provider 接口
- **WHEN** 实现自定义 Provider
- **THEN** SHALL 声明 `provider_name`、`provider_version`、`embedding_dimension` 属性，接收已解码图片批次并返回归一化二维向量数组

#### Scenario: 默认 Provider
- **WHEN** 未指定 Provider 且 `semantic` 可选依赖已安装
- **THEN** 使用 `onnx_dinov2_small` 默认 Provider（模型 `onnx-community/dinov2-small-ONNX`，dim=384，source=cls_token，normalize=true）

#### Scenario: Provider 注入
- **WHEN** 通过 registry 构造参数注入自定义 Provider
- **THEN** Provider 对象 SHALL NOT 出现在 config hash 或 state.json 中

### Requirement: Faiss ANN 索引
系统 SHALL 使用 Faiss Flat IP 索引存储和查询 embedding 相似度。

#### Scenario: 索引构建
- **WHEN** embedding 计算完成
- **THEN** SHALL 构建 Faiss Flat IP 索引（归一化 embedding + inner product 近似 cosine similarity）

#### Scenario: Artifact 存储
- **WHEN** 运行完成
- **THEN** embedding SHALL 存储到 `artifacts/semantic_embeddings/{embeddings.npy, image_ids.parquet, manifest.json}`；Faiss 索引 SHALL 存储到 `artifacts/semantic_index/{faiss.index, manifest.json}`；关系表 SHALL 输出到 `relations/semantic_duplicate_pairs.parquet`

### Requirement: 可选依赖组
语义去重所需的深度学习依赖 SHALL 作为可选安装项。

#### Scenario: 依赖组定义
- **WHEN** 安装 image_gallery 包
- **THEN** SHALL 提供 `semantic` 可选依赖组（包含 `onnxruntime`、`huggingface-hub`、`faiss-cpu`），主包不强制安装

#### Scenario: 依赖缺失
- **WHEN** `semantic` 依赖组未安装
- **THEN** 使用默认 Provider 时 SHALL 抛出明确错误，说明需要安装 `semantic` 依赖组

#### Scenario: 不改变现有语义
- **WHEN** 语义去重算子运行
- **THEN** SHALL NOT 改变 pHash 算子行为和现有 export/preview 语义
