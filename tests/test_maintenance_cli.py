from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit.maintenance import cli
from sdetkit.maintenance.checks import lint_check, security_check
from sdetkit.maintenance.types import MaintenanceContext
from sdetkit.security import SecurityError


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


def test_write_output_blocks_parent_traversal(tmp_path: Path, monkeypatch) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    with pytest.raises(SecurityError, match="unsafe path rejected"):
        cli._write_output("../escape.json", "content")


def test_security_check_uses_new_findings_when_baseline_exists(tmp_path: Path, monkeypatch) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "security.baseline.json").write_text('{"findings": []}\n', encoding="utf-8")

    class Result:
        returncode = 0
        stdout = json.dumps(
            {
                "findings": [{"severity": "warn", "rule_id": "SEC_X"}],
                "new_findings": [],
            }
        )
        stderr = ""

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: Result())
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is True


def test_security_check_requires_repeated_failure(tmp_path: Path, monkeypatch) -> None:
    class Result:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    calls = iter(
        [
            Result(0, json.dumps({"findings": [{"severity": "warn", "rule_id": "SEC_X"}]})),
            Result(0, "security fix complete; files changed: 0\n"),
            Result(0, json.dumps({"findings": []})),
        ]
    )

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: next(calls))
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is True
    assert out.summary == "security check recovered after auto-fix/retry"


def test_security_check_fix_mode_applies_fix_before_follow_up(tmp_path: Path, monkeypatch) -> None:
    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    seen: list[list[str]] = []

    def _run(cmd: list[str], *, cwd: Path):
        seen.append(cmd)
        if cmd[-2:] == ["fix", "--apply"]:
            return Result(0, "fixed")
        check_index = sum(1 for item in seen if item[-1] == "none")
        if check_index == 1:
            return Result(0, json.dumps({"findings": [{"severity": "warn", "rule_id": "SEC_X"}]}))
        return Result(0, json.dumps({"findings": []}))

    monkeypatch.setattr(security_check, "run_cmd", _run)
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=True,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is True
    assert any(action.id == "security-fix" and action.applied for action in out.actions)
    assert any(cmd[-2:] == ["fix", "--apply"] for cmd in seen)


def test_security_check_first_occurrence_is_recorded_not_failed(
    tmp_path: Path, monkeypatch
) -> None:
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "findings": [
                    {"severity": "warn", "fingerprint": "fp-1", "rule_id": "SEC_EMPTY_EXCEPT"}
                ]
            }
        )

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: Result())
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is True
    assert out.details["repeated"] is False
    assert "non-repeated" in out.summary


def test_security_check_repeated_fingerprint_fails(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".sdetkit" / "out"
    state.mkdir(parents=True)
    (state / "maintenance-security-check.json").write_text(
        json.dumps({"fingerprints": ["fp-1"]}) + "\n", encoding="utf-8"
    )

    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "findings": [
                    {"severity": "warn", "fingerprint": "fp-1", "rule_id": "SEC_EMPTY_EXCEPT"}
                ]
            }
        )

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: Result())
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is False
    assert out.details["repeated"] is True
    assert "reproduced" in out.summary


def test_security_check_autofix_runs_without_fix_flag(tmp_path: Path, monkeypatch) -> None:
    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    seen: list[list[str]] = []

    def _run(cmd: list[str], *, cwd: Path):
        seen.append(cmd)
        if cmd[-2:] == ["fix", "--apply"]:
            return Result(0, "fixed")
        check_index = sum(1 for item in seen if item[-1] == "none")
        if check_index == 1:
            return Result(
                0, json.dumps({"findings": [{"severity": "warn", "fingerprint": "fp-2"}]})
            )
        return Result(0, json.dumps({"findings": []}))

    monkeypatch.setattr(security_check, "run_cmd", _run)
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is True
    assert any(cmd[-2:] == ["fix", "--apply"] for cmd in seen)


def test_security_check_details_include_findings_digest(tmp_path: Path, monkeypatch) -> None:
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "findings": [
                    {
                        "severity": "warn",
                        "fingerprint": "fp-7",
                        "rule_id": "SEC_EMPTY_EXCEPT",
                        "path": "src/sdetkit/doctor.py",
                        "line": 12,
                        "message": "except block silently swallows errors via pass.",
                    }
                ]
            }
        )

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: Result())
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={"SDETKIT_MAINTENANCE_SECURITY_AUTOFIX": "0"},
        logger=object(),
    )

    out = security_check.run(ctx)
    follow_up = out.details["follow_up"]
    assert follow_up["findings_total"] == 1
    assert follow_up["top_rules"][0]["rule_id"] == "SEC_EMPTY_EXCEPT"
    assert follow_up["top_paths"][0]["path"] == "src/sdetkit/doctor.py"
    assert follow_up["sample_findings"][0]["line"] == 12
    assert follow_up["remediation_hints"][0]["rule_id"] == "SEC_EMPTY_EXCEPT"
    assert "except blocks" in follow_up["remediation_hints"][0]["hint"]


def test_security_check_summary_includes_repeated_fingerprint_hint(
    tmp_path: Path, monkeypatch
) -> None:
    state = tmp_path / ".sdetkit" / "out"
    state.mkdir(parents=True)
    (state / "maintenance-security-check.json").write_text(
        json.dumps({"fingerprints": ["fp-r1"]}) + "\n", encoding="utf-8"
    )

    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "findings": [
                    {
                        "severity": "warn",
                        "fingerprint": "fp-r1",
                        "rule_id": "SEC_EMPTY_EXCEPT",
                    }
                ]
            }
        )

    monkeypatch.setattr(security_check, "run_cmd", lambda _cmd, cwd: Result())
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe=sys.executable,
        mode="full",
        fix=False,
        env={"SDETKIT_MAINTENANCE_SECURITY_AUTOFIX": "0"},
        logger=object(),
    )

    out = security_check.run(ctx)
    assert out.ok is False
    assert "fp-r1" in out.summary
    assert out.details["repeated_fingerprints"] == ["fp-r1"]
