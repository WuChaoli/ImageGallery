.PHONY: lint lint_package lint_tests lint_diff format format_check test test_real test_all check security security_secrets security_dependencies security_workflows security_exceptions package package_smoke sbom help

# 兼容入口：权威实现位于 `uv run python -m tools.ci <task>`。

lint:
	uv run python -m tools.ci lint

lint_package:
	uv run python -m tools.ci lint-package

lint_tests:
	uv run python -m tools.ci lint-tests

lint_diff:
	uv run python -m tools.ci lint-diff

format:
	uv run python -m tools.ci format

format_check:
	uv run python -m tools.ci format-check

test:
	uv run python -m tools.ci test

test_real:
	uv run python -m tools.ci test-real

test_all:
	uv run python -m tools.ci test-all

check:
	uv run python -m tools.ci check

security_secrets:
	uv run python -m tools.ci security-secrets

security_dependencies:
	uv run python -m tools.ci security-dependencies

security_workflows:
	uv run python -m tools.ci security-workflows

security_exceptions:
	uv run python -m tools.ci security-exceptions

security:
	uv run python -m tools.ci security

package:
	uv run python -m tools.ci package

package_smoke:
	uv run python -m tools.ci package-smoke

sbom:
	uv run python -m tools.ci sbom

help:
	$(info Python CI 权威入口: uv run python -m tools.ci <task>)
	$(info Makefile 当前仅作为兼容别名保留。)
	uv run python -m tools.ci --help
