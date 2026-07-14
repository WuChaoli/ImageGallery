## MODIFIED Requirements

### Requirement: Agent provides direct runnable commands

AI Agent SHALL provide both `make` and direct `uv run` equivalents for development commands。默认测试命令 SHALL 排除 `slow` 测试，并 SHALL 提供独立的真实数据验收与完整测试命令。

#### Scenario: Test command includes uv alternative
- **WHEN** Agent references the default test command
- **THEN** both `make test` and an equivalent `uv run --group test pytest -m "not slow" ...` command SHALL be provided

#### Scenario: Real dataset test command includes uv alternative
- **WHEN** Agent references the real dataset acceptance command
- **THEN** both the corresponding make target and an equivalent `uv run --group test pytest -m "real_dataset" ...` command SHALL be provided

#### Scenario: Lint command includes uv alternative
- **WHEN** Agent references a lint command
- **THEN** both `make lint` and equivalent direct commands (`python -m ruff check src tests`, `python -m pyright src/image_gallery`) SHALL be provided
