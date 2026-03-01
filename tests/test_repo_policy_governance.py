from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from sdetkit import cli


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(args)
        return Result(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")


def test_policy_lint_requires_owner_and_justification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SDETKIT_TODAY", "2026-01-02")
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
allowlist = [{ rule_id = "CORE_MISSING_SECURITY_MD", path = "SECURITY.md" }]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "policy",
            "lint",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "error",
        ]
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 1
    assert payload["counts"]["errors"] == 2
    assert {item["code"] for item in payload["errors"]} == {
        "missing_owner",
        "missing_justification",
    }


def test_expired_allowlist_is_actionable_and_counted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SDETKIT_TODAY", "2026-02-01")
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
fail_on = "none"
[[tool.sdetkit.repo_audit.allowlist]]
rule_id = "CORE_MISSING_SECURITY_MD"
path = "SECURITY.md"
owner = "sec@acme"
justification = "temp"
expires = "2026-01-31"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"]
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert any(item["rule_id"] == "CORE_MISSING_SECURITY_MD" for item in payload["findings"])
    assert payload["summary"]["policy"]["suppressed_active"] == 0
    assert payload["summary"]["policy"]["suppressed_expired"] >= 1


def test_today_env_controls_expiration_deterministically(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
[[tool.sdetkit.repo_audit.allowlist]]
rule_id = "CORE_MISSING_SECURITY_MD"
path = "SECURITY.md"
owner = "sec@acme"
justification = "temp"
expires = "2026-01-31"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    monkeypatch.setenv("SDETKIT_TODAY", "2026-01-30")
    active = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "none",
        ]
    )
    active_payload = json.loads(active.stdout)
    assert all(item["rule_id"] != "CORE_MISSING_SECURITY_MD" for item in active_payload["findings"])

    monkeypatch.setenv("SDETKIT_TODAY", "2026-02-01")
    expired = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "none",
        ]
    )
    expired_payload = json.loads(expired.stdout)
    assert any(
        item["rule_id"] == "CORE_MISSING_SECURITY_MD" for item in expired_payload["findings"]
    )


def test_policy_export_is_deterministic_and_sorted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SDETKIT_TODAY", "2026-01-01")
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
[[tool.sdetkit.repo_audit.allowlist]]
rule_id = "CORE_MISSING_SECURITY_MD"
path = "SECURITY.md"
owner = "sec@acme"
justification = "waiver"
created = "2025-12-01"
expires = "2026-12-31"
ticket = "SEC-123"
[[tool.sdetkit.repo_audit.allowlist]]
rule_id = "CORE_MISSING_CODE_OF_CONDUCT_MD"
path = "CODE_OF_CONDUCT.md"
owner = "eng@acme"
justification = "migration"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    first = runner.invoke(["repo", "policy", "export", str(tmp_path), "--allow-absolute-path"])
    second = runner.invoke(["repo", "policy", "export", str(tmp_path), "--allow-absolute-path"])
    assert first.exit_code == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["schema_version"] == "sdetkit.policy.v1"
    assert payload["allowlist"] == sorted(
        payload["allowlist"],
        key=lambda item: (item["rule_id"], item["path"], item.get("contains") or ""),
    )


def test_org_pack_entrypoint_discovery_affects_audit_selection(tmp_path: Path, monkeypatch) -> None:
    from sdetkit import plugins

    class FakePack:
        pack_name = "org-acme"
        rule_ids = ("CORE_MISSING_SECURITY_MD",)
        defaults = {"fail_on": "error"}

    class FakeEP:
        name = "acme-pack"

        def load(self):
            return FakePack

    class EPs:
        def select(self, *, group: str):
            if group == "sdetkit.repo_audit_packs":
                return [FakeEP()]
            return []

    monkeypatch.setattr(plugins.importlib_metadata, "entry_points", lambda: EPs())
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
fail_on = "none"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--org-pack",
            "org-acme",
        ]
    )
    assert result.exit_code == 1


def test_unknown_ids_warn_deterministically(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SDETKIT_TODAY", "2026-01-01")
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
disable_rules = ["NOT_REAL"]
severity_overrides = { "ALSO_UNKNOWN" = "warn" }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "policy",
            "lint",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "none",
        ]
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert [item["code"] for item in payload["warnings"]] == [
        "unknown_disable_rule",
        "unknown_severity_override",
    ]
