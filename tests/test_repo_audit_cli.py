from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


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


def test_repo_audit_text_and_json_are_deterministic(tmp_path: Path, capsys) -> None:
    _seed_min_repo(tmp_path)

    rc = cli.main(["repo", "audit", str(tmp_path), "--allow-absolute-path"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "Result: PASS" in text
    assert "OSS readiness files" in text

    rc2 = cli.main(["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc2 == 0
    j1 = json.loads(capsys.readouterr().out)

    rc3 = cli.main(["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc3 == 0
    j2 = json.loads(capsys.readouterr().out)
    assert j1 == j2
    assert j1["summary"]["ok"] is True


def test_repo_audit_fails_when_license_and_workflow_missing(tmp_path: Path, capsys) -> None:
    _seed_min_repo(tmp_path)
    (tmp_path / "LICENSE").unlink()
    (tmp_path / ".github" / "workflows" / "security.yml").unlink()

    rc = cli.main(["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    failed = {item["key"] for item in report["checks"] if item["status"] == "fail"}
    assert "oss_readiness" in failed
    assert "ci_security_workflows" in failed


def test_repo_audit_out_respects_force(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    report = tmp_path / "audit.json"
    report.write_text("old", encoding="utf-8")

    rc = cli.main(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--out",
            "audit.json",
        ]
    )
    assert rc == 2

    rc2 = cli.main(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--out",
            "audit.json",
            "--force",
        ]
    )
    assert rc2 == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"]["ok"] is True
