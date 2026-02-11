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
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("guide\n", encoding="utf-8")
    (root / "CODE_OF_CONDUCT.md").write_text("code\n", encoding="utf-8")
    (root / "SECURITY.md").write_text("security\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("changes\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "noxfile.py").write_text("\n", encoding="utf-8")
    (root / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "requirements-test.txt").write_text("pytest\n", encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    issue = root / ".github" / "ISSUE_TEMPLATE"
    issue.mkdir(parents=True, exist_ok=True)
    (issue / "config.yml").write_text("blank_issues_enabled: false\n", encoding="utf-8")
    (root / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text("## Summary\n", encoding="utf-8")


def _audit_json(runner: CliRunner, root: Path, *extra: str) -> Result:
    return runner.invoke(
        ["repo", "audit", str(root), "--allow-absolute-path", "--format", "json", *extra]
    )


def test_config_precedence_cli_over_config_over_profile(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
profile = "default"
fail_on = "none"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "CONTRIBUTING.md").unlink(missing_ok=True)
    runner = CliRunner()

    result_config = _audit_json(runner, tmp_path)
    assert result_config.exit_code == 0

    result_cli = _audit_json(runner, tmp_path, "--fail-on", "warn")
    assert result_cli.exit_code == 1


def test_exclude_patterns_disable_rules_and_allowlist_suppress(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs" / "huge.bin").write_bytes(b"x" * (6 * 1024 * 1024))
    (tmp_path / "CODE_OF_CONDUCT.md").unlink(missing_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
exclude_paths = ["docs/**"]
disable_rules = ["CORE_MISSING_CODE_OF_CONDUCT_MD"]
allowlist = [
  { rule_id = "CORE_MISSING_CODE_OF_CONDUCT_MD", path = "CODE_OF_CONDUCT.md", contains = "missing required file" }
]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = _audit_json(runner, tmp_path)
    payload = json.loads(result.stdout)
    assert payload["summary"]["policy"]["suppressed_by_policy"] >= 1
    assert all(item["rule_id"] != "CORE_MISSING_CODE_OF_CONDUCT_MD" for item in payload["findings"])


def test_severity_overrides_apply_for_gating(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").unlink(missing_ok=True)
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
severity_overrides = { "CORE_MISSING_CONTRIBUTING_MD" = "info" }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = _audit_json(runner, tmp_path, "--fail-on", "warn")
    payload = json.loads(result.stdout)
    overridden = [
        item for item in payload["findings"] if item["rule_id"] == "CORE_MISSING_CONTRIBUTING_MD"
    ]
    assert overridden
    assert {item["severity"] for item in overridden} == {"info"}
    assert result.exit_code == 0


def test_baseline_create_stable_schema_and_order(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    baseline = tmp_path / ".sdetkit" / "audit-baseline.json"

    first = runner.invoke(["repo", "baseline", "create", str(tmp_path), "--allow-absolute-path"])
    assert first.exit_code == 0
    doc1 = json.loads(baseline.read_text(encoding="utf-8"))

    second = runner.invoke(["repo", "baseline", "create", str(tmp_path), "--allow-absolute-path"])
    assert second.exit_code == 0
    doc2 = json.loads(baseline.read_text(encoding="utf-8"))

    assert doc1["schema_version"] == "1.0"
    assert doc1 == doc2
    assert doc1["entries"] == sorted(
        doc1["entries"], key=lambda x: (x["path"], x["rule_id"], x["fingerprint"])
    )


def test_baseline_check_new_resolved_unchanged_and_update(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()

    create = runner.invoke(["repo", "baseline", "create", str(tmp_path), "--allow-absolute-path"])
    assert create.exit_code == 0

    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / "CODE_OF_CONDUCT.md").unlink(missing_ok=True)

    check = runner.invoke(
        [
            "repo",
            "baseline",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--fail-on",
            "warn",
            "--diff",
        ]
    )
    assert check.exit_code == 1
    assert "NEW:" in check.stdout and "RESOLVED:" in check.stdout and "UNCHANGED:" in check.stdout

    update = runner.invoke(
        [
            "repo",
            "baseline",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--fail-on",
            "none",
            "--update",
        ]
    )
    assert update.exit_code == 0


def test_repo_audit_baseline_suppression_hides_gating_noise(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").unlink(missing_ok=True)
    runner = CliRunner()
    create = runner.invoke(["repo", "baseline", "create", str(tmp_path), "--allow-absolute-path"])
    assert create.exit_code == 0

    result = _audit_json(runner, tmp_path)
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["summary"]["policy"]["suppressed_by_baseline"] >= 1
    assert payload["summary"]["policy"]["actionable"] == 0


def test_update_baseline_is_idempotent(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    baseline = tmp_path / ".sdetkit" / "audit-baseline.json"
    runner.invoke(["repo", "baseline", "create", str(tmp_path), "--allow-absolute-path"])

    first = _audit_json(runner, tmp_path, "--update-baseline")
    assert first.exit_code == 0
    snapshot1 = baseline.read_text(encoding="utf-8")

    second = _audit_json(runner, tmp_path, "--update-baseline")
    assert second.exit_code == 0
    snapshot2 = baseline.read_text(encoding="utf-8")

    assert snapshot1 == snapshot2
    assert first.stdout == second.stdout
