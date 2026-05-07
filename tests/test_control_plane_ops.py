from __future__ import annotations

import json
from pathlib import Path

from sdetkit import ops_control


def test_ops_init_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert ops_control.init_layout(force=False) == 0
    assert (tmp_path / ".sdetkit" / "config.toml").is_file()
    original = (tmp_path / ".sdetkit" / "config.toml").read_text(encoding="utf-8")
    assert ops_control.init_layout(force=False) == 0
    assert (tmp_path / ".sdetkit" / "config.toml").read_text(encoding="utf-8") == original


def test_ops_plan_deterministic_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    ops_control.init_layout()
    p1 = ops_control.plan("default", apply=False, no_cache=True)
    p2 = ops_control.plan("default", apply=False, no_cache=True)
    assert [item["task"] for item in p1] == [item["task"] for item in p2]


def test_ops_cache_changes_on_file_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    ops_control.init_layout()

    monkeypatch.setitem(
        ops_control.BUILTIN_TASKS,
        "cache-probe",
        ops_control.TaskDef(
            "cache-probe",
            ("python3", "-c", "raise SystemExit(0)"),
        ),
    )
    (tmp_path / ".sdetkit" / "config.toml").write_text(
        '[profiles]\ndefault=["cache-probe"]\nci=["cache-probe"]\nlocal=["cache-probe"]\n',
        encoding="utf-8",
    )
    (tmp_path / "sample.py").write_text("print('a')\n", encoding="utf-8")
    assert (
        ops_control.run(
            "default", jobs=1, apply=False, no_cache=False, fail_fast=False, keep_going=True
        )
        == 0
    )
    first = ops_control.plan("default", apply=False, no_cache=False)
    (tmp_path / "sample.py").write_text("print('b')\n", encoding="utf-8")
    second = ops_control.plan("default", apply=False, no_cache=False)
    assert any(item["cached"] for item in first)
    assert any(not item["cached"] for item in second)


def test_ops_fail_fast_vs_keep_going(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    ops_control.init_layout()
    custom = tmp_path / ".sdetkit" / "config.toml"
    custom.write_text(
        '[profiles]\ndefault = ["quality", "ci", "doctor"]\nci = ["quality", "ci", "doctor"]\nlocal = ["doctor"]\n',
        encoding="utf-8",
    )
    rc_fast = ops_control.run(
        "default", jobs=1, apply=False, no_cache=True, fail_fast=True, keep_going=False
    )
    rc_keep = ops_control.run(
        "default", jobs=1, apply=False, no_cache=True, fail_fast=False, keep_going=True
    )
    assert rc_fast in {0, 1}
    assert rc_keep in {0, 1}


def test_ops_plan_cli_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert ops_control.cli(["init"]) == 0
    assert ops_control.cli(["plan", "--profile", "default"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "default"


def test_security_scan_task_is_non_gating() -> None:
    task = ops_control.BUILTIN_TASKS["security-scan"]
    assert "--fail-on" in task.command
    idx = task.command.index("--fail-on")
    assert task.command[idx + 1] == "none"


def test_report_build_task_uses_valid_cli_flags() -> None:
    task = ops_control.BUILTIN_TASKS["report-build"]
    assert task.command[:5] == ("python3", "-m", "sdetkit", "report", "build")
    assert "--history-dir" in task.command
    assert "--output" in task.command
    dot_index = task.command.index(".")
    assert task.command[dot_index - 1] == "--history-dir"


def test_repo_audit_task_is_non_gating() -> None:
    task = ops_control.BUILTIN_TASKS["repo-audit"]
    assert "--fail-on" in task.command
    idx = task.command.index("--fail-on")
    assert task.command[idx + 1] == "none"
    assert "--force" in task.command
