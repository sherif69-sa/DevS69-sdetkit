from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit import cli


def test_enterprise_workflow_and_sarif_output(tmp_path: Path, capsys) -> None:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        "on: pull_request_target\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: curl https://x | bash\n",
        encoding="utf-8",
    )
    rc = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--profile",
            "enterprise",
            "--format",
            "sarif",
        ]
    )
    rc = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--profile", "enterprise", "--format", "sarif"])
    assert rc == 1
    sarif = json.loads(capsys.readouterr().out)
    assert sarif["version"] == "2.1.0"
    ids = {r["ruleId"] for r in sarif["runs"][0]["results"]}
    assert "gha_hardening/unpinned_action" in ids
    assert "gha_hardening/pull_request_target" in ids


def test_enterprise_baseline_suppresses_findings(tmp_path: Path, capsys) -> None:
    (tmp_path / "secrets.txt").write_text("token=shhh\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            [
                {
                    "path": "secrets.txt",
                    "check": "secret_scan",
                    "code": "auth_header",
                    "reason": "test fixture",
                    "expires": "2999-01-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--baseline",
            "baseline.json",
        ]
    )
    rc = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json", "--baseline", "baseline.json"])
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert all(f["code"] != "auth_header" for f in report["findings"])


def test_enterprise_changed_only_uses_diff_base(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)

    (tmp_path / "old.txt").write_text("token=abc\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True)

    subprocess.run(
        ["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "new.txt").write_text("bad  \n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "new"], cwd=tmp_path, check=True, capture_output=True)

    rc = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--changed-only",
            "--diff-base",
            "main",
        ]
    )
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    paths = {f["path"] for f in report["findings"]}
    assert "new.txt" in paths
    assert "old.txt" not in paths


def test_repo_check_writes_sbom(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\ndependencies=[\n'requests>=2',\n]\n",
        encoding="utf-8",
    )
    rc = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--profile",
            "enterprise",
            "--sbom-out",
            "sbom.json",
        ]
    )
    assert rc == 1
    sbom = json.loads((tmp_path / "sbom.json").read_text(encoding="utf-8"))
    names = {c["name"] for c in sbom["components"]}
    assert "requests" in names
