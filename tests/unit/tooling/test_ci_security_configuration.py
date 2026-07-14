"""验证 CI 安全门槛的仓库配置契约。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_yaml(path: Path) -> dict[str, object]:
    """使用不会把 `on` 解析为布尔值的 loader 读取 YAML。"""
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


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
    assert set(workflow["jobs"]) == {"lint", "test", "package"}
    assert "pull_request" in workflow["on"]
    assert "master" in workflow["on"]["pull_request"]["branches"]
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "uv sync --extra dev --frozen" in text
    assert "uv sync --all-extras --frozen" in text
    assert "uv sync --group dev" not in text


def test_security_workflow_covers_required_scanners() -> None:
    """安全工作流必须覆盖密钥、依赖和 workflow 审计。"""
    workflow = _load_yaml(WORKFLOWS / "security.yml")
    assert set(workflow["jobs"]) == {"secrets", "dependencies", "workflows"}
    text = (WORKFLOWS / "security.yml").read_text(encoding="utf-8")
    assert "gitleaks" in text.lower()
    assert "security_dependencies" in text
    assert "security_workflows" in text


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


def test_makefile_exposes_reproducible_security_and_package_targets() -> None:
    """本地入口必须覆盖 CI 使用的安全与构建检查。"""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in (
        "security_secrets:",
        "security_dependencies:",
        "security_workflows:",
        "security_exceptions:",
        "package:",
        "package_smoke:",
    ):
        assert target in text


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
    result = subprocess.run(
        [sys.executable, ROOT / "tools" / "check_security_exceptions.py", config],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 1
    assert "expired" in result.stdout
