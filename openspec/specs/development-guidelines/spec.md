# Development Guidelines

## Purpose

定义 AI Agent 在本仓库开发时应遵循的行为规范和检查清单，确保提交一致、接口稳定、测试完整、代码安全。

## Requirements

### Requirement: Agent follows structured commit and PR conventions

AI Agent SHALL follow Conventional Commits format with required scope for all commit titles and PR titles.

#### Scenario: Commit with valid scope
- **WHEN** Agent creates a commit for a change in the `cleaning` module
- **THEN** commit title SHALL follow `type(cleaning): description` format

#### Scenario: Commit without scope is rejected
- **WHEN** Agent creates a commit title without a scope
- **THEN** Agent SHALL add the appropriate scope

#### Scenario: Branch name follows convention
- **WHEN** Agent creates a branch
- **THEN** branch name SHALL follow `<username>/<scope>/<short-description>` pattern

#### Scenario: PR description includes why and release notes
- **WHEN** Agent creates a PR description
- **THEN** description SHALL explain the problem and solution ("why" not "what"), and include a `## Release note` section for new features or behavior-changing fixes

### Requirement: Agent protects public API stability

AI Agent SHALL verify public API stability before modifying any exported function, class, or method.

#### Scenario: Check export status before modification
- **WHEN** Agent is about to modify a function
- **THEN** Agent SHALL check if the function is exported in `__init__.py`

#### Scenario: Check existing usage before signature change
- **WHEN** Agent considers changing a function signature
- **THEN** Agent SHALL search for existing usage patterns in tests and examples

#### Scenario: New parameters use keyword-only
- **WHEN** Agent adds a new parameter to a public function
- **THEN** the parameter SHALL be keyword-only (`*, new_param: type = default`)

#### Scenario: Breaking change warning
- **WHEN** Agent identifies a change that could break existing callers
- **THEN** Agent SHALL warn the developer and propose backward-compatible alternatives

### Requirement: Agent follows test coverage checklist

AI Agent SHALL ensure every new feature or bugfix is covered by tests following a standardized checklist.

#### Scenario: Happy path test exists
- **WHEN** Agent implements a new feature
- **THEN** a unit test covering the happy path SHALL be created

#### Scenario: Edge cases are tested
- **WHEN** Agent implements a new feature or bugfix
- **THEN** edge cases and error conditions SHALL be covered by tests

#### Scenario: Tests are deterministic
- **WHEN** Agent writes tests
- **THEN** tests SHALL NOT depend on network calls (unit tests), external state, or non-deterministic behavior

#### Scenario: Tests fail when logic breaks
- **WHEN** Agent's new logic is removed or broken
- **THEN** the corresponding tests SHALL fail

### Requirement: Agent follows security constraints

AI Agent SHALL NOT use dangerous patterns in production code.

#### Scenario: No eval on user input
- **WHEN** Agent writes code that processes external data
- **THEN** `eval()`, `exec()`, and `pickle.load()` SHALL NOT be called on user-controlled input

#### Scenario: Proper exception handling
- **WHEN** Agent writes exception handling code
- **THEN** bare `except:` SHALL NOT be used; exception type SHALL be specified

#### Scenario: Resource cleanup
- **WHEN** Agent opens files, connections, or other resources
- **THEN** resources SHALL be properly closed (use context managers or try/finally)

### Requirement: Agent provides direct runnable commands

AI Agent SHALL provide both `make` and direct `uv run` equivalents for development commands。默认测试命令 SHALL 排除 `slow` 测试，并 SHALL 提供独立的真实数据验收与完整测试命令。

#### Scenario: Test command includes uv alternative
- **WHEN** Agent references the default test command
- **THEN** both `make test` and an equivalent `uv run pytest -m "not slow" ...` command SHALL be provided

#### Scenario: Real dataset test command includes uv alternative
- **WHEN** Agent references the real dataset acceptance command
- **THEN** both the corresponding make target and an equivalent `uv run pytest -m "real_dataset" ...` command SHALL be provided

#### Scenario: Lint command includes uv alternative
- **WHEN** Agent references a lint command
- **THEN** both `make lint` and equivalent direct commands (`python -m ruff check src tests`, `python -m pyright src/image_gallery`) SHALL be provided
