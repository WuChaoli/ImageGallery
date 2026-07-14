## ADDED Requirements

### Requirement: Notebook Helpers 包结构
系统 SHALL 提供 `notebooks/_helpers/` 包，为 Notebook 验证提供初始化和轻量装配支持。

#### Scenario: 模块组成
- **WHEN** 导入 `notebooks._helpers`
- **THEN** SHALL 包含 4 个模块：`paths`（仓库根目录定位、输出目录重置）、`storage`（`.env` 加载、MinIO 连接）、`datasets`（sample_1000 路径和 Dataset/DataFrame 加载）、`cleaning_configs`（算子配置列表和 TOML 示例）

#### Scenario: Helper 职责边界
- **WHEN** 使用 Notebook helpers
- **THEN** helper SHALL 只负责初始化和轻量装配（路径、环境变量、storage、Dataset、算子配置）；Notebook SHALL 负责组装、运行 BasicCleaner、读取 run 产物并展示统计与抽样

#### Scenario: Helper 不进入 src
- **WHEN** 检查 helpers 位置
- **THEN** helpers SHALL 位于 `notebooks/_helpers/`，NOT 位于 `src/image_gallery/`

### Requirement: 确定性采样
数据集构建 SHALL 使用固定随机种子确保采样可重复。

#### Scenario: 采样种子
- **WHEN** 构建 sample_1000 数据集
- **THEN** SHALL 使用 `random_state=20260706` 进行确定性采样

#### Scenario: Cleaner runtime 采样种子
- **WHEN** 使用 `sample={"n": 100}` 运行清洗
- **THEN** seed SHALL 由 dataset fingerprint + graph plan hash 的 SHA-256 截断整数自动派生

### Requirement: Notebook 验证策略
Notebook 验证 SHALL 以人工运行为主，自动化覆盖以单测和集成测试为主。

#### Scenario: CI 策略
- **WHEN** 运行 CI 测试套件
- **THEN** Notebook SHALL NOT 自动执行；自动化覆盖以 helper 单测和集成测试为主

#### Scenario: MinIO 依赖
- **WHEN** Notebook 需要 MinIO 连接
- **THEN** SHALL 强依赖 MinIO，不实现 `.env` 缺失时的降级模式；MinIO 不可用时 `pytest.skip()`

#### Scenario: Helper 独立测试
- **WHEN** 测试 helpers
- **THEN** SHALL 有独立 unit tests（`test_paths_helper.py`、`test_storage_helper.py`、`test_datasets_helper.py`、`test_cleaning_configs_helper.py`）

### Requirement: 算子配置预设
Helpers SHALL 提供多组预定义的算子配置，用于不同验证场景。

#### Scenario: 配置预设列表
- **WHEN** 调用 cleaning_configs 模块
- **THEN** SHALL 提供：`get_cleaning_v3_first_batch_operator_configs()`（10 个基础算子）、`get_cleaning_v3_light_risk_operator_configs()`（6 个轻量风险算子）、`get_cleaning_v3_quality_baseline_operator_configs()`（3 个质量基线算子）、`get_cleaning_v3_non_semantic_all_operator_configs()`（全部非语义算子）

#### Scenario: TOML 示例
- **WHEN** 调用 `get_cleaning_v3_toml_examples()`
- **THEN** SHALL 返回可直接使用的 TOML 配置字符串示例
