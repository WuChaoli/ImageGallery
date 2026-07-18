## Why

`CleanerResult` 同时负责运行产物定位、JSON/Parquet 解析、导出、预览、解释与清理，`toml_config.py` 同时负责配置入口、模板生成和全部运行策略解析，导致高耦合文件难以安全演进。需要先用 characterization tests 固定现有公开与持久化语义，再把可独立变化的职责收敛到私有模块。

## What Changes

- 补充 `CleanerResult` 状态、结果、预览、导出以及 TOML/YAML 配置选择与校验的 characterization tests。
- 将运行结果产物读取、导出/调试包和预览选项解析从 `CleanerResult` 门面中提取为私有协作模块。
- 将 TOML 模板生成与 `NodePolicy` 解析从 `CleanerConfig` 入口中提取为私有配置模块。
- 保持 `image_gallery.cleaning` 公开导出、公开签名、返回值、异常文本和磁盘持久化格式不变。
- 不新增运行能力，不修改 Cleaning Runtime、算子协议或 Dataset 导出协议。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cleaning-preview`: 明确 `CleanerResult` 重构后状态、结果、导出、预览、解释和清理的可观察语义保持不变。
- `cleaning-config`: 明确 TOML/YAML 配置入口、选择规则和校验错误在私有职责拆分后保持不变。

## Impact

- 影响 `src/image_gallery/cleaning/result.py`、`toml_config.py`、`recipe.py` 及新增的模块私有协作文件。
- 增加 `tests/unit/cleaning/` 下的结果与配置 characterization tests。
- 不影响公开 API、依赖、运行目录布局、Parquet/JSON/SQLite schema 或调用方迁移成本。
