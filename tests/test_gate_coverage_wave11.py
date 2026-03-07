from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from sdetkit import gate


def _release_ns(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "root": ".",
        "format": "json",
        "out": None,
        "dry_run": False,
        "release_full": False,
        "playbooks_all": False,
        "playbooks_legacy": False,
        "playbooks_aliases": False,
        "playbook_name": [],
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_normalize_release_cmd_rewrites_python_and_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cmd = [gate.sys.executable, "-m", "sdetkit", "gate", "fast", str(root), f"{root}/x"]
    normalized = gate._normalize_release_cmd(cmd, root)
    assert normalized[0] == "python"
    assert normalized[-2] == "<repo>"
    assert normalized[-1] == "<repo>/x"


def test_run_release_failure_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        failed = "playbooks" in cmd
        return {
            "cmd": cmd,
            "rc": 1 if failed else 0,
            "ok": not failed,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "boom" if failed else "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_release(_release_ns())
    assert rc == 2
    out = capsys.readouterr().out
    assert '"failed_steps": ["playbooks_validate"]' in out
    assert any(c[3:5] == ["playbooks", "validate"] for c in calls)


def test_baseline_returns_fast_rc_when_profile_run_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["baseline", "check", "--", "--only", "not-a-step"])
    assert rc == 2


def test_playbooks_validate_args_name_branch() -> None:
    ns = _release_ns(playbook_name=["a", "b"])
    assert gate._playbooks_validate_args(ns) == [
        "--name",
        "a",
        "--name",
        "b",
        "--format",
        "json",
    ]
