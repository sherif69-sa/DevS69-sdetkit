from __future__ import annotations

import json
import subprocess
import sys

from sdetkit.maintenance import cli
from sdetkit.maintenance.checks import lint_check
from sdetkit.maintenance.types import MaintenanceContext


def test_quick_mode_returns_stable_schema() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.maintenance", "--mode", "quick", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}
    payload = json.loads(proc.stdout)
    assert set(payload) == {"ok", "score", "checks", "recommendations", "meta"}
    assert payload["meta"]["schema_version"] == "1.0"
    assert set(payload["meta"]) >= {
        "schema_version",
        "generated_at",
        "mode",
        "fix",
        "python",
        "duration_seconds",
        "had_crash",
    }
    for value in payload["checks"].values():
        assert set(value) >= {"ok", "summary", "details", "actions"}


def test_json_output_contains_only_json_stdout() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.maintenance", "--format", "json", "--mode", "quick"],
        capture_output=True,
        text=True,
    )
    json.loads(proc.stdout)


def test_deterministic_mode_is_byte_identical_across_runs() -> None:
    cmd = [
        sys.executable,
        "-m",
        "sdetkit.maintenance",
        "--format",
        "json",
        "--mode",
        "quick",
        "--deterministic",
    ]
    proc_a = subprocess.run(cmd, capture_output=True, text=True)
    proc_b = subprocess.run(cmd, capture_output=True, text=True)

    assert proc_a.returncode in {0, 1}
    assert proc_b.returncode in {0, 1}
    assert proc_a.stdout == proc_b.stdout


def test_missing_tool_is_graceful(monkeypatch) -> None:
    monkeypatch.setattr(lint_check.shutil, "which", lambda _name: None)
    ctx = MaintenanceContext(
        repo_root=cli.Path.cwd(),
        python_exe=sys.executable,
        mode="quick",
        fix=False,
        env={},
        logger=object(),
    )
    result = lint_check.run(ctx)
    assert result.ok is False
    assert "not available" in result.summary
    assert result.details["missing_tool"] == "ruff"


def test_fix_mode_records_actions() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit.maintenance",
            "--mode",
            "quick",
            "--fix",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode in {0, 1}
    payload = json.loads(proc.stdout)
    lint_actions = payload["checks"]["lint_check"]["actions"]
    assert lint_actions


def test_render_markdown_escapes_table_breaking_content() -> None:
    report = {
        "ok": False,
        "score": 0,
        "checks": {
            "lint|check\nname": {
                "ok": False,
                "summary": "summary with | pipe\nand `ticks` <html>",
                "details": {},
                "actions": [],
            }
        },
        "recommendations": ["Fix | this\nnow <soon>"],
        "meta": {"mode": "quick"},
    }

    markdown = cli._render_markdown(report)
    lines = markdown.splitlines()
    check_rows = [
        line for line in lines if line.startswith("| ") and ("PASS" in line or "FAIL" in line)
    ]

    assert len(check_rows) == 1
    assert "lint\\|check name" in check_rows[0]
    assert "summary with \\| pipe and \\`ticks\\` &lt;html&gt;" in check_rows[0]
    assert "\n" not in check_rows[0]
    assert "- Fix \\| this now &lt;soon&gt;" in markdown


def test_render_markdown_escapes_exception_derived_summary(monkeypatch) -> None:
    def _crash(_ctx: MaintenanceContext):
        raise RuntimeError("boom |\n<bad>`")

    monkeypatch.setattr(cli, "checks_for_mode", lambda _mode: [("crash|check", _crash)])

    ctx = MaintenanceContext(
        repo_root=cli.Path.cwd(),
        python_exe=sys.executable,
        mode="quick",
        fix=False,
        env={},
        logger=object(),
    )

    report = cli._build_report(ctx)
    markdown = cli._render_markdown(report)

    check_rows = [
        line for line in markdown.splitlines() if line.startswith("| ") and "FAIL" in line
    ]
    assert len(check_rows) == 1
    assert "crash\\|check" in check_rows[0]
    assert "check crashed: boom \\| &lt;bad&gt;\\`" in check_rows[0]
