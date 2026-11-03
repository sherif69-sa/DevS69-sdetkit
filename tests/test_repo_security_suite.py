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


def _audit_security(runner: CliRunner, root: Path, fmt: str = "json") -> Result:
    return runner.invoke(
        [
            "repo",
            "audit",
            str(root),
            "--allow-absolute-path",
            "--pack",
            "security",
            "--fail-on",
            "none",
            "--format",
            fmt,
        ]
    )


def test_security_secrets_detection_and_fixture_allowlist(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("A=1\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("A=1\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("A=example\n", encoding="utf-8")
    (tmp_path / "id_rsa").write_text("nope\n", encoding="utf-8")
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    (tmp_path / "tests" / "fixtures" / "id_rsa").write_text("fixture\n", encoding="utf-8")

    runner = CliRunner()
    result = _audit_security(runner, tmp_path)
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    findings = payload["findings"]
    assert any(f["rule_id"] == "SEC_SECRETS_ENV_IN_REPO" and f["path"] == ".env" for f in findings)
    assert any(
        f["rule_id"] == "SEC_SECRETS_ENV_IN_REPO" and f["path"] == ".env.local" for f in findings
    )
    assert not any(f["path"] == ".env.example" for f in findings)
    assert any(
        f["rule_id"] == "SEC_SECRETS_ENV_IN_REPO"
        and f["path"] == "id_rsa"
        and f["severity"] == "error"
        for f in findings
    )
    assert any(
        f["rule_id"] == "SEC_SECRETS_TEST_FIXTURES_ALLOW"
        and f["path"] == "tests/fixtures/id_rsa"
        and f["severity"] == "warn"
        for f in findings
    )


def test_security_secrets_respects_exclude_patterns(tmp_path: Path) -> None:
    (tmp_path / ".env.local").write_text("A=1\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--pack",
            "security",
            "--exclude",
            ".env.*",
            "--fail-on",
            "none",
            "--format",
            "json",
        ]
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert all(item["rule_id"] != "SEC_SECRETS_ENV_IN_REPO" for item in payload["findings"])


def test_security_workflow_scanning_refs_and_permissions(tmp_path: Path) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        """
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - uses: actions/setup-python@v5
      - uses: owner/tool@0123456789abcdef0123456789abcdef01234567
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = _audit_security(runner, tmp_path)
    payload = json.loads(result.stdout)
    findings = payload["findings"]

    assert any(item["rule_id"] == "SEC_GH_ACTIONS_PINNING" for item in findings)
    assert any(item["rule_id"] == "SEC_GH_PERMISSIONS_MISSING" for item in findings)
    assert not any(
        "setup-python" in item["message"] and item["rule_id"] == "SEC_GH_ACTIONS_PINNING"
        for item in findings
    )


def test_security_codeowners_locations(tmp_path: Path) -> None:
    runner = CliRunner()
    r1 = _audit_security(runner, tmp_path)
    p1 = json.loads(r1.stdout)
    assert any(item["rule_id"] == "SEC_GH_CODEOWNERS_MISSING" for item in p1["findings"])

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CODEOWNERS").write_text("* @org/team\n", encoding="utf-8")
    r2 = _audit_security(runner, tmp_path)
    p2 = json.loads(r2.stdout)
    assert all(item["rule_id"] != "SEC_GH_CODEOWNERS_MISSING" for item in p2["findings"])


def test_security_fix_audit_templates_idempotent_and_force(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    runner = CliRunner()

    first = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--pack",
            "security",
            "--apply",
            "--force",
        ]
    )
    assert first.exit_code == 0
    assert (tmp_path / "SECURITY.md").exists()
    assert (tmp_path / ".github" / "CODEOWNERS").exists()
    assert (tmp_path / ".github" / "dependabot.yml").exists()
    assert (tmp_path / ".pre-commit-config.yaml").exists()

    second = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--pack",
            "security",
            "--apply",
            "--force",
        ]
    )
    assert second.exit_code == 0
    assert "no changes" in second.stdout


def test_security_json_and_sarif_include_pack_fixable_and_rule_help(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _audit_security(runner, tmp_path, fmt="json")
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    security_md = next(
        item for item in payload["findings"] if item["rule_id"] == "SEC_GH_SECURITY_MD_MISSING"
    )
    assert security_md["pack"] == "security"
    assert security_md["fixable"] is True

    sarif_result = _audit_security(runner, tmp_path, fmt="sarif")
    sarif = json.loads(sarif_result.stdout)
    run = sarif["runs"][0]
    rules = {item["id"]: item for item in run["tool"]["driver"]["rules"]}
    assert "SEC_GH_SECURITY_MD_MISSING" in rules
    assert rules["SEC_GH_SECURITY_MD_MISSING"]["help"]["text"]
    assert any(res["ruleId"] == "SEC_GH_SECURITY_MD_MISSING" for res in run["results"])


def test_security_pack_skips_virtualenvs_and_dependency_trees(tmp_path: Path) -> None:
    for rel in (
        ".venv/lib/python3.11/site-packages/certifi/cacert.pem",
        "venv/lib/site-packages/pkg/server.key",
        "node_modules/foo/server.key",
        ".venv-3.12/lib/.env",
    ):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "server.key").write_text("x\n", encoding="utf-8")

    payload = json.loads(_audit_security(CliRunner(), tmp_path).stdout)

    flagged = sorted(
        {f["path"] for f in payload["findings"] if f["rule_id"].startswith("SEC_SECRETS")}
    )
    assert flagged == ["deploy/server.key"]
