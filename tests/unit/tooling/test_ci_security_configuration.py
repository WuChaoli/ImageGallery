"""验证 CI 安全门槛的仓库配置契约。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_pyproject() -> dict[str, object]:
    """读取 pyproject 配置。"""
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, object]:
    """使用不会把 `on` 解析为布尔值的 loader 读取 YAML。"""
    # BaseLoader 只产生字符串/容器，用于保持 GitHub Actions 的 `on` 键语义。
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)  # noqa: S506


def test_pull_request_workflows_use_read_only_permissions_and_pinned_actions() -> None:
    """PR 工作流必须最小授权并固定第三方 Action。"""
    for name in ("ci.yml", "security.yml"):
        path = WORKFLOWS / name
        workflow = _load_yaml(path)
        assert workflow["permissions"] == {"contents": "read"}

        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "uses:" not in line:
                continue
            reference = line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0].strip()
            revision = reference.rsplit("@", maxsplit=1)[1].split(maxsplit=1)[0]
            assert len(revision) == 40
            assert all(char in "0123456789abcdef" for char in revision)


def test_ci_workflow_has_stable_required_jobs() -> None:
    """质量工作流必须暴露稳定且唯一的 required job 名称。"""
    workflow = _load_yaml(WORKFLOWS / "ci.yml")
    assert set(workflow["jobs"]) == {"lint", "test", "coverage", "compatibility", "package"}
    assert "pull_request" in workflow["on"]
    assert "master" in workflow["on"]["pull_request"]["branches"]
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "uv sync --extra dev --frozen" in text
    assert "uv sync --all-extras --frozen" in text
    assert "uv sync --group dev" not in text
    assert "uv run python -m tools.ci format-check" in text
    assert "uv run python -m tools.ci lint" in text
    assert "uv run python -m tools.ci docs" in text
    assert "uv run python -m tools.ci test" in text
    assert "uv run python -m tools.ci package" in text
    assert "uv run python -m tools.ci package-validate" in text
    assert "uv run python -m tools.ci package-smoke" in text
    assert "make " not in text


def test_security_workflow_covers_required_scanners() -> None:
    """安全工作流必须覆盖密钥、依赖和 workflow 审计。"""
    workflow = _load_yaml(WORKFLOWS / "security.yml")
    assert set(workflow["jobs"]) == {"secrets", "dependencies", "workflows"}
    text = (WORKFLOWS / "security.yml").read_text(encoding="utf-8")
    assert "gitleaks" in text.lower()
    assert "uv run python -m tools.ci security-dependencies" in text
    assert "uv run python -m tools.ci security-workflows" in text
    assert "make " not in text


def test_dependabot_updates_python_and_actions_dependencies() -> None:
    """Dependabot 必须覆盖 Python 与 GitHub Actions 更新。"""
    config = _load_yaml(ROOT / ".github" / "dependabot.yml")
    ecosystems = {item["package-ecosystem"] for item in config["updates"]}
    assert ecosystems == {"uv", "github-actions"}


def test_security_exceptions_document_required_governance_fields() -> None:
    """安全豁免清单必须声明可审计字段。"""
    config = _load_yaml(ROOT / ".security-exceptions.yml")
    assert config["version"] == "1"
    assert isinstance(config["exceptions"], list)
    required = set(config["required-fields"])
    assert required == {"id", "tool", "scope", "reason", "owner", "expires"}


def test_python_ci_is_the_only_current_command_entrypoint() -> None:
    """当前权威内容不得重新引入 Makefile 开发入口。"""
    assert not (ROOT / "Makefile").exists()
    authoritative_paths = [ROOT / "AGENTS.md", ROOT / "README.md"]
    authoritative_paths.extend((ROOT / "openspec" / "specs").glob("*/spec.md"))
    for path in authoritative_paths:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"\bmake[ \t]+[a-zA-Z0-9_-]+", text) is None, path


def test_agents_documents_split_pre_pr_checks() -> None:
    """PR 前策略必须逐项列出全部硬门禁与失败处理。"""
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    pre_pr_section = text.split("### PR 提交前手动验证", maxsplit=1)[1]
    commands = [
        f"uv run python -m tools.ci {task}"
        for task in (
            "format-check",
            "lint",
            "docs",
            "test",
            "coverage",
            "security",
            "package",
            "package-validate",
            "package-smoke",
        )
    ]
    positions = [pre_pr_section.index(command) for command in commands]
    assert positions == sorted(positions)
    assert "任一命令失败时立即停止" in text
    assert "不能替代完整的 PR 前手动验证" in text
    assert "MinIO、sample_1000 或真实数据" in text
    assert "slow、并发、缓存、状态恢复或资源生命周期" in text
    assert "uv run python -m tools.ci test-real" in pre_pr_section
    assert "uv run python -m tools.ci test-all" in pre_pr_section


def test_scheduled_and_release_workflows_use_python_ci_entrypoint() -> None:
    """定时安全和发布工作流必须使用 Python CI 入口。"""
    scheduled = (WORKFLOWS / "scheduled-security.yml").read_text(encoding="utf-8")
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "uv run python -m tools.ci security-exceptions" in scheduled
    assert "uv run python -m tools.ci security-dependencies" in scheduled
    assert "uv run python -m tools.ci security-workflows" in scheduled
    assert "uv run python -m tools.ci package" in release
    assert "uv run python -m tools.ci package-smoke" in release
    assert "uv run python -m tools.ci sbom" in release
    assert "uv run python -m tools.ci release-license" in release
    assert "cyclonedx-py environment" not in release
    assert "make " not in scheduled
    assert "make " not in release


def test_codeql_advanced_workflow_is_pinned_and_scans_supported_languages() -> None:
    """CodeQL advanced setup 必须覆盖 Python 与 Actions。"""
    path = WORKFLOWS / "codeql.yml"
    workflow = _load_yaml(path)
    assert workflow["permissions"] == {"contents": "read", "security-events": "write"}
    assert "pull_request" in workflow["on"]
    assert "push" in workflow["on"]
    assert "schedule" in workflow["on"]
    assert set(workflow["jobs"]) == {"codeql"}
    assert set(workflow["jobs"]["codeql"]["strategy"]["matrix"]["language"]) == {"python", "actions"}
    text = path.read_text(encoding="utf-8")
    assert "github/codeql-action/init@02c5e83432fe5497fd85b873b6c9f16a8578e1d9" in text
    assert "github/codeql-action/analyze@02c5e83432fe5497fd85b873b6c9f16a8578e1d9" in text


def test_python_versions_are_explicit_and_do_not_use_runner_defaults() -> None:
    """最低与最新稳定 Python 必须由 workflow 显式安装。"""
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.10"' in text
    assert 'python-version: ["3.14"]' in text
    assert "python-version: ${{ matrix.python-version }}" in text
    assert "uv run python -m tools.ci test-compat" in text


def test_deep_quality_checks_are_scheduled_and_not_pr_required() -> None:
    """随机、重复、Vulture、链接与 mutation 只能作为定时报告。"""
    workflow = _load_yaml(WORKFLOWS / "deep-quality.yml")
    assert "pull_request" not in workflow["on"]
    assert {"randomized-tests", "stability-tests", "advisory-reports", "supported-python-report"} == set(
        workflow["jobs"]
    )
    text = (WORKFLOWS / "deep-quality.yml").read_text(encoding="utf-8")
    assert "--randomly-seed=${{ github.run_id }}" in text
    assert "-m stability --count=5" in text
    assert "vulture src tools --min-confidence 90" in text
    assert "tools/check_external_links.py" in text
    assert "mutmut run" in text


def test_expired_security_exception_is_rejected(tmp_path: Path) -> None:
    """过期安全豁免必须导致治理检查失败。"""
    config = tmp_path / "exceptions.yml"
    config.write_text(
        """version: 1
required-fields: [id, tool, scope, reason, owner, expires]
exceptions:
  - id: GHSA-example
    tool: pip-audit
    scope: package@example
    reason: temporary mitigation
    owner: maintainer
    expires: 2000-01-01
""",
        encoding="utf-8",
    )
    # argv 固定调用仓库内脚本，临时配置路径作为独立参数传递。
    result = subprocess.run(  # noqa: S603
        [sys.executable, ROOT / "tools" / "check_security_exceptions.py", config],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 1
    assert "expired" in result.stdout


def test_ruff_uses_only_approved_quality_gate_rules() -> None:
    """Ruff 必须启用精选规则且保留明确禁止项。"""
    config = _load_pyproject()
    ruff = config["tool"]["ruff"]
    selected = set(ruff["lint"]["select"])
    assert {
        "S",
        "BLE001",
        "TRY004",
        "PT",
        "C901",
        "C4",
        "SIM102",
        "SIM103",
        "SIM114",
        "SIM115",
        "RET504",
    } <= selected
    assert {"TRY003", "RUF002", "RUF003", "SIM108", "RET501", "ANN"}.isdisjoint(selected)
    assert ruff["lint"]["mccabe"]["max-complexity"] == 15
    assert set(ruff["lint"]["per-file-ignores"]["tests/**"]) == {"D", "S101", "S105", "S106", "S108"}


def test_pytest_uses_strict_configuration() -> None:
    """pytest marker 与配置拼写错误必须直接失败。"""
    config = _load_pyproject()
    pytest_options = config["tool"]["pytest"]["ini_options"]
    assert pytest_options["strict_markers"] is True
    assert pytest_options["strict_config"] is True
    assert "stability" in " ".join(pytest_options["markers"])


def test_documentation_tools_preserve_balanced_policy() -> None:
    """文档检查必须具备项目词典且不审查中文语法。"""
    config = _load_pyproject()
    codespell = config["tool"]["codespell"]
    dictionary = set(codespell["ignore-words-list"].split(","))
    assert {"cleane", "fo", "nd", "statics", "te"} <= dictionary
    assert "docs-backup.tar.gz" in codespell["skip"]
    assert "tools/check_docs.py" in (ROOT / "tools" / "ci.py").read_text(encoding="utf-8")


def test_broad_type_suppression_is_rejected(tmp_path: Path) -> None:
    """无具体规则的类型忽略必须被治理脚本拒绝。"""
    source = tmp_path / "bad.py"
    source.write_text("value = unknown()  # type: ignore\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        [sys.executable, ROOT / "tools" / "check_suppressions.py", source],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "specific rule" in result.stdout


def test_specific_suppressions_are_accepted(tmp_path: Path) -> None:
    """限定到具体规则的 suppression 可以通过。"""
    source = tmp_path / "good.py"
    source.write_text(
        "value = unknown()  # type: ignore[name-defined]\n"
        "other = call()  # pyright: ignore[reportCallIssue]\n"
        "unused = 1  # noqa: F841\n",
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, ROOT / "tools" / "check_suppressions.py", source],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
