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


def _seed_min_repo(root: Path) -> None:
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
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
    (wf / "security.yml").write_text("name: security\n", encoding="utf-8")


def test_repo_audit_json_schema_and_stable_keys(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"]
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0.0"
    assert list(payload.keys()) == [
        "checks",
        "findings",
        "root",
        "schema_version",
        "summary",
        "suppressed",
    ]


def test_repo_audit_sarif_has_required_fields(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    (tmp_path / "LICENSE").unlink()

    runner = CliRunner()
    result = runner.invoke(
        ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "sarif"]
    )
    assert result.exit_code == 1

    sarif = json.loads(result.stdout)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "sdetkit"
    rule_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
    first_result = run["results"][0]
    assert "ruleId" in first_result
    assert first_result["ruleId"] in rule_ids
    assert "text" in first_result["message"]
    uri = first_result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri
    assert not uri.startswith("/")


def test_repo_audit_sarif_normalizes_absolute_like_paths_to_relative(tmp_path: Path) -> None:
    from sdetkit import repo

    payload = {
        "findings": [
            {
                "check": "repo_audit",
                "code": "missing_repo_hygiene_item",
                "severity": "error",
                "message": "required repository hygiene item is missing: LICENSE",
                "path": "/tmp/example/LICENSE",
                "line": 1,
                "column": 1,
            }
        ]
    }

    sarif = repo._to_sarif(payload)
    uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "tmp/example/LICENSE"


def test_repo_audit_fail_on_exit_codes(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)

    big_file = tmp_path / "huge.bin"
    big_file.write_bytes(b"x" * (6 * 1024 * 1024))

    runner = CliRunner()
    args = ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"]

    fail_none = runner.invoke([*args, "--fail-on", "none"])
    assert fail_none.exit_code == 0

    fail_warn = runner.invoke([*args, "--fail-on", "warn"])
    assert fail_warn.exit_code == 1

    fail_error = runner.invoke([*args, "--fail-on", "error"])
    assert fail_error.exit_code == 0


def test_repo_audit_output_file_writes_without_stdout(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    report = tmp_path / "audit.json"

    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--output",
            "audit.json",
            "--force",
        ]
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"]["ok"] is True
