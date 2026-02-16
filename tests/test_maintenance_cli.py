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
