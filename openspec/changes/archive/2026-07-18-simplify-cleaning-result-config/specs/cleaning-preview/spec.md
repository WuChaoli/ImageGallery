## ADDED Requirements

### Requirement: CleanerResult 结果门面语义稳定

系统 SHALL 在内部职责拆分后保持 `CleanerResult` 的状态、结果、导出、预览、解释与清理语义不变，并继续读取既有运行目录格式。

#### Scenario: 缺失状态数据库

- **WHEN** 运行目录没有 `run_state.sqlite` 或没有对应 run 记录
- **THEN** `CleanerResult.status()` 返回 `"running"`

#### Scenario: 结果产物读取

- **WHEN** 调用 `state()`、`result()`、`explain()` 或 `preview()` 读取既有 Parquet、JSON 和 state 文件
- **THEN** 返回内容、缺失 manifest/state 回退和无效持久化值的异常语义与重构前一致

#### Scenario: 运行产物导出

- **WHEN** 调用 table、manifest、relation、debug bundle 或 Dataset 导出入口
- **THEN** 目标文件内容、返回对象以及无效 kind/name 的异常语义与重构前一致

#### Scenario: Operator HTML 预览

- **WHEN** 调用 `preview_html()` 并指定 operator、actions、filters、排序或数量覆盖
- **THEN** operator action 列选择、过滤顺序、预览策略覆盖、HTML 内容和 fallback Dataset 路径语义与重构前一致

#### Scenario: 清理运行目录

- **WHEN** 调用 `cleanup()`
- **THEN** 仅删除 `cache_root/run_id` 对应目录且不影响其他运行目录
