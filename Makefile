.PHONY: lint test check format lint_diff lint_package lint_tests security security_secrets security_dependencies security_workflows security_exceptions package package_smoke sbom help

# Windows 兼容：使用 Git Bash 作为 shell
ifeq ($(OS),Windows_NT)
    SHELL := C:\Program Files\Git\bin\sh.exe
endif

# ── 变量 ──────────────────────────────────────────
TEST_FILE     ?= tests/
PYTEST_EXTRA  ?=

# ── 静态检查 ──────────────────────────────────────
# ruff: 代码风格 + docstring（D 规则组）；pyright: 类型检查（warning 不阻断）

lint:
	uv run ruff check src tests
	uv run pyright src/image_gallery

lint_package:
	uv run ruff check src
	uv run pyright src/image_gallery

lint_tests:
	uv run ruff check tests

lint_diff:
	uv run ruff check $$(git diff --relative --name-only --diff-filter=d master -- '*.py')
	uv run pyright src/image_gallery

# ── 格式化 ──────────────────────────────────────────
format:
	-uv run ruff check --fix src tests
	uv run ruff format src tests

# ── 测试 ──────────────────────────────────────────
# -n auto: 按 CPU 核数并行执行
# --disable-socket: 拦截单元测试中的意外网络请求
# --allow-unix-socket: 允许 Unix socket（pytest-xdist 需要）
test:
	uv run pytest -n auto --disable-socket --allow-unix-socket $(PYTEST_EXTRA) $(TEST_FILE)

# ── 一键检查 ──────────────────────────────────────
check: lint test

# ── 安全与发布检查 ──────────────────────────────────
security_secrets:
	gitleaks git --redact --no-banner .

security_dependencies:
	uv run pip-audit --progress-spinner off

security_workflows:
	uv run zizmor .github/workflows

security_exceptions:
	uv run python tools/check_security_exceptions.py

security: security_exceptions security_secrets security_dependencies security_workflows

package:
	uv run python -m build --outdir .tmp/ci-dist

package_smoke:
	uv run --isolated --no-project --with "$$(ls -t .tmp/ci-dist/*.whl | head -1)" python -c "import image_gallery"

sbom:
	uv run cyclonedx-py environment --output-format JSON --output-file .tmp/image-gallery.cdx.json

# ── 帮助 ──────────────────────────────────────────
help:
	$(info ----)
	$(info lint              - 全量静态检查（ruff 代码风格 + docstring + pyright 类型检查）)
	$(info lint_package      - 仅检查 src/ 目录的代码风格和类型)
	$(info lint_tests        - 仅检查 tests/ 目录的代码风格（跳过类型检查）)
	$(info lint_diff         - 仅检查当前分支相比 master 的变更文件)
	$(info format            - 一键 ruff 格式化 + lint 修复)
	$(info test              - 运行测试（并行 -n auto + 网络隔离 --disable-socket）)
	$(info   TEST_FILE=path  - 指定测试文件或目录（默认 tests/）)
	$(info   PYTEST_EXTRA=   - 传递额外 pytest 参数)
	$(info check             - lint + test 全量检查)
	$(info security          - 依赖、工作流与安全豁免检查)
	$(info package           - 构建 wheel 与 sdist 到 .tmp/ci-dist)
	$(info package_smoke     - 在隔离环境安装并导入最新 wheel)
	$(info sbom              - 生成 CycloneDX SBOM)
	$(info help              - 显示此帮助)
