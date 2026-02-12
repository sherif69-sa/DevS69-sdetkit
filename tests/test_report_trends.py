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


def test_run_record_json_v1_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    args = [
        "repo",
        "audit",
        str(tmp_path),
        "--allow-absolute-path",
        "--format",
        "json",
        "--json-schema",
        "v1",
    ]
    first = runner.invoke(args)
    second = runner.invoke(args)
    assert first.exit_code == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["schema_version"] == "sdetkit.audit.run.v1"
    assert payload["source"]["captured_at"] == "2023-11-14T22:13:20Z"
    assert payload["source"]["commit_sha"] == "abc123"
    assert payload["findings"] == sorted(
        payload["findings"],
        key=lambda x: (
            {"info": 0, "warn": 1, "error": 2}.get(x["severity"], 2),
            x["rule_id"],
            x["path"],
            x["fingerprint"],
        ),
    )


def test_report_ingest_idempotent_uses_content_hash(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    run_path = tmp_path / "run.json"
    audit = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--json-schema",
            "v1",
            "--emit-run-record",
            str(run_path),
            "--force",
        ]
    )
    assert audit.exit_code == 0

    history = tmp_path / ".sdetkit" / "audit-history"
    first = runner.invoke(["report", "ingest", str(run_path), "--history-dir", str(history)])
    second = runner.invoke(["report", "ingest", str(run_path), "--history-dir", str(history)])
    assert first.exit_code == 0
    assert second.exit_code == 0

    index = json.loads((history / "index.json").read_text(encoding="utf-8"))
    assert len(index["runs"]) == 1
    digest = index["runs"][0]["sha256"]
    assert (history / f"{digest}.json").exists()


def test_report_diff_detects_new_resolved_and_fail_on(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    run1 = tmp_path / "run1.json"
    run2 = tmp_path / "run2.json"

    first = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--emit-run-record",
            str(run1),
            "--force",
        ]
    )
    assert first.exit_code == 0

    (tmp_path / "CONTRIBUTING.md").unlink()
    second = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--emit-run-record",
            str(run2),
            "--force",
            "--fail-on",
            "none",
        ]
    )
    assert second.exit_code == 0

    diff = runner.invoke(
        ["report", "diff", "--from", str(run1), "--to", str(run2), "--fail-on", "warn"]
    )
    assert diff.exit_code == 1
    assert "NEW:" in diff.stdout
    assert "RESOLVED:" in diff.stdout


def test_report_build_deterministic_html_and_md(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    history = tmp_path / ".sdetkit" / "audit-history"
    run1 = tmp_path / "run1.json"
    run2 = tmp_path / "run2.json"

    runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--emit-run-record",
            str(run1),
            "--force",
        ]
    )
    (tmp_path / "SECURITY.md").unlink()
    runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--emit-run-record",
            str(run2),
            "--force",
            "--fail-on",
            "none",
        ]
    )

    runner.invoke(["report", "ingest", str(run1), "--history-dir", str(history)])
    runner.invoke(["report", "ingest", str(run2), "--history-dir", str(history)])

    html1 = tmp_path / "report1.html"
    html2 = tmp_path / "report2.html"
    md1 = tmp_path / "report1.md"
    md2 = tmp_path / "report2.md"
    assert (
        runner.invoke(
            ["report", "build", "--history-dir", str(history), "--output", str(html1)]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            ["report", "build", "--history-dir", str(history), "--output", str(html2)]
        ).exit_code
        == 0
    )
    assert html1.read_text(encoding="utf-8") == html2.read_text(encoding="utf-8")
    assert "Top recurring rules" in html1.read_text(encoding="utf-8")

    assert (
        runner.invoke(
            [
                "report",
                "build",
                "--history-dir",
                str(history),
                "--output",
                str(md1),
                "--format",
                "md",
            ]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            [
                "report",
                "build",
                "--history-dir",
                str(history),
                "--output",
                str(md2),
                "--format",
                "md",
            ]
        ).exit_code
        == 0
    )
    assert md1.read_text(encoding="utf-8") == md2.read_text(encoding="utf-8")
    assert "delta vs previous" in md1.read_text(encoding="utf-8")


def test_step_summary_writes_expected_markdown(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    runner = CliRunner()
    summary = tmp_path / "step-summary.md"
    run1 = tmp_path / "run1.json"

    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--step-summary",
            "--emit-run-record",
            str(run1),
            "--force",
        ]
    )
    assert result.exit_code == 0
    content = summary.read_text(encoding="utf-8")
    assert "sdetkit repo audit summary" in content
    assert "Top 10 actionable findings" in content
    assert "sdetkit repo fix-audit --dry-run" in content
