from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sdetkit import cli, repo


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
    issue = root / ".github" / "ISSUE_TEMPLATE"
    issue.mkdir(parents=True, exist_ok=True)
    (issue / "config.yml").write_text("blank_issues_enabled: false\n", encoding="utf-8")
    (root / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text("## Summary\n", encoding="utf-8")
    (wf / "security.yml").write_text("name: security\n", encoding="utf-8")


def _invoke(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def test_precommit_install_dry_run_does_not_write(tmp_path: Path) -> None:
    code, out, err = _invoke(
        ["dev", "precommit", "install", str(tmp_path), "--dry-run", "--allow-absolute-path"]
    )
    assert code == 0
    assert err == ""
    assert "dry-run" in out
    assert not (tmp_path / ".pre-commit-config.yaml").exists()


def test_precommit_install_apply_and_idempotent(tmp_path: Path) -> None:
    code, _, _ = _invoke(
        [
            "dev",
            "precommit",
            "install",
            str(tmp_path),
            "--apply",
            "--mode",
            "changed-only",
            "--allow-absolute-path",
        ]
    )
    assert code == 0
    target = tmp_path / ".pre-commit-config.yaml"
    content = target.read_text(encoding="utf-8")
    assert "id: sdetkit-repo-audit" in content
    assert "--changed-only" in content

    code2, out2, _ = _invoke(
        ["dev", "precommit", "install", str(tmp_path), "--dry-run", "--allow-absolute-path"]
    )
    assert code2 == 0
    assert "already up to date" in out2
    assert target.read_text(encoding="utf-8") == content


def test_precommit_install_refuses_incompatible_without_force(tmp_path: Path) -> None:
    target = tmp_path / ".pre-commit-config.yaml"
    target.write_text("minimum_pre_commit_version: '3.0.0'\n", encoding="utf-8")
    code, _, err = _invoke(
        ["dev", "precommit", "install", str(tmp_path), "--apply", "--allow-absolute-path"]
    )
    assert code == 2
    assert "unable to merge" in err


def test_precommit_install_diff_is_deterministic(tmp_path: Path) -> None:
    target = tmp_path / ".pre-commit-config.yaml"
    target.write_text("repos:\n  - repo: local\n    hooks: []\n", encoding="utf-8")
    args = [
        "dev",
        "precommit",
        "install",
        str(tmp_path),
        "--dry-run",
        "--diff",
        "--allow-absolute-path",
    ]
    code1, out1, _ = _invoke(args)
    code2, out2, _ = _invoke(args)
    assert code1 == 0
    assert code2 == 0
    assert out1 == out2


def test_ide_diagnostics_schema_and_ordering(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").unlink()
    (tmp_path / "LICENSE").unlink()
    ide_out = tmp_path / "diag.json"

    code, _, _ = _invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--ide",
            "generic",
            "--ide-output",
            str(ide_out),
        ]
    )
    assert code == 1
    payload = json.loads(ide_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.ide.diagnostics.v1"
    assert payload["diagnostics"] == sorted(
        payload["diagnostics"],
        key=lambda x: (x["path"], x["line"], x.get("col", 0), x["code"], x["message"]),
    )
    assert all(item["severity"] in {"info", "warn", "error"} for item in payload["diagnostics"])
    assert all(item["code"] for item in payload["diagnostics"])


def test_ide_diagnostics_include_suppressed_toggle(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").unlink()

    code, out, _ = _invoke(
        ["repo", "audit", str(tmp_path), "--allow-absolute-path", "--format", "json"]
    )
    assert code == 1
    audit = json.loads(out)
    entries = repo._baseline_entries_from_findings(audit["findings"])
    baseline = tmp_path / ".sdetkit" / "repo-audit-baseline.json"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(
        json.dumps(
            {"schema_version": "1.0", "entries": entries}, ensure_ascii=True, sort_keys=True
        ),
        encoding="utf-8",
    )

    ide_default = tmp_path / "default.json"
    rc_default, _, _ = _invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--ide-output",
            str(ide_default),
            "--fail-on",
            "none",
            "--baseline",
            str(baseline),
        ]
    )
    assert rc_default == 0
    default_doc = json.loads(ide_default.read_text(encoding="utf-8"))
    assert default_doc["diagnostics"] == []

    ide_all = tmp_path / "all.json"
    rc_all, _, _ = _invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--ide-output",
            str(ide_all),
            "--include-suppressed",
            "--fail-on",
            "none",
            "--baseline",
            str(baseline),
        ]
    )
    assert rc_all == 0
    all_doc = json.loads(ide_all.read_text(encoding="utf-8"))
    assert len(all_doc["diagnostics"]) >= 1


def test_dev_wrappers_match_core_commands(tmp_path: Path) -> None:
    _seed_min_repo(tmp_path)
    (tmp_path / "CONTRIBUTING.md").unlink()

    rc_repo, out_repo, _ = _invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--pack",
            "core",
            "--changed-only",
            "--fail-on",
            "error",
        ]
    )
    rc_dev, out_dev, _ = _invoke(["dev", "audit", str(tmp_path), "--allow-absolute-path"])
    assert rc_dev == rc_repo
    assert out_dev == out_repo

    rc_fix, out_fix, _ = _invoke(["dev", "fix", str(tmp_path), "--allow-absolute-path"])
    assert rc_fix == 0
    assert "repo fix-audit (dry-run)" in out_fix
