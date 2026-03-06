from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

import pytest

from sdetkit import gate


def _ns(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = dict(
        root=".",
        only=None,
        skip=None,
        list_steps=False,
        fix=False,
        fix_only=False,
        no_doctor=False,
        no_ci_templates=False,
        no_ruff=False,
        no_mypy=False,
        no_pytest=False,
        strict=False,
        format="text",
        out=None,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
        stable_json=False,
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


def _ok(cmd: list[str], cwd: Path) -> dict[str, object]:
    return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}


def test_format_md_includes_failed_steps_block() -> None:
    payload = {
        "ok": False,
        "root": ".",
        "steps": [{"id": "ruff", "ok": True, "duration_ms": 1, "rc": 0}],
        "failed_steps": ["doctor", "mypy"],
    }
    out = gate._format_md(payload)
    assert "#### Failed steps" in out
    assert "- `doctor`" in out
    assert "- `mypy`" in out


def test_run_fast_hits_doctor_ci_mypy_and_pytest_args(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok(cmd, cwd)

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(
            strict=True,
            no_ruff=True,
            mypy_args="src tests",
            pytest_args="-q tests/test_gate_fast.py",
            format="text",
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "gate fast: OK" in out
    assert any(cmd[3] == "doctor" and "medium" in cmd for cmd in calls)
    assert any("validate-templates" in " ".join(cmd) for cmd in calls)
    assert any(cmd[1:3] == ["-m", "mypy"] and cmd[-2:] == ["src", "tests"] for cmd in calls)
    assert any(
        cmd[1:3] == ["-m", "pytest"] and cmd[-2:] == ["-q", "tests/test_gate_fast.py"]
        for cmd in calls
    )


def test_run_fast_md_branch_with_failures(monkeypatch, capsys) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        ok = "mypy" not in cmd
        return {
            "cmd": cmd,
            "rc": 0 if ok else 1,
            "ok": ok,
            "duration_ms": 2,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(_ns(no_ruff=True, format="md"))
    out = capsys.readouterr().out
    assert rc == 2
    assert "#### Failed steps" in out


def test_playbooks_validate_args_aliases_branch() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )
    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]


def test_baseline_relative_path_is_resolved_under_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snaps/custom.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )
    assert rc == 0
    assert (tmp_path / "snaps" / "custom.json").exists()


def test_baseline_returns_fast_rc_when_profile_execution_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "_run_fast", lambda ns: 7)
    rc = gate.main(["baseline", "check", "--", "--no-doctor"])
    assert rc == 7


def test_baseline_handles_non_json_exception_during_cur_obj_parse(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_fast(ns: argparse.Namespace) -> int:
        # baseline captures stdout from this recursive call
        sys.stdout.write('{"ok": true, "steps": []}\n')
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)

    real_loads = gate.json.loads

    calls = {"n": 0}

    def boom(text: str, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(gate.json, "loads", boom)
    rc = gate.main(["baseline", "check"])
    out = capsys.readouterr().out
    # restore for assertion parsing
    monkeypatch.setattr(gate.json, "loads", real_loads)
    obj = json.loads(out)
    assert rc == 2
    assert obj["snapshot_diff_ok"] is False


def test_baseline_diff_jsondecodeerror_fallbacks_and_diff_newline(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{bad snapshot", encoding="utf-8")

    def fake_run_fast(ns: argparse.Namespace) -> int:
        sys.stdout.write('{"ok": false, "steps": []}')
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)
    monkeypatch.setattr(gate.difflib, "unified_diff", lambda *a, **k: iter(["DIFF-NO-NL"]))

    real_loads = gate.json.loads
    calls = {"n": 0}

    def selective_loads(text: str, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        # Force the line-501 branch once in diff generation (parse current side).
        if calls["n"] == 3:
            raise json.JSONDecodeError("forced", text, 0)
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(gate.json, "loads", selective_loads)

    rc = gate.main(["baseline", "check", "--diff"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 2
    assert payload["snapshot_diff"].endswith("\n")
    assert payload["snapshot_diff_ok"] is False


def test_baseline_parsed_is_none_when_cur_text_is_invalid_json(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_fast(ns: argparse.Namespace) -> int:
        sys.stdout.write("not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)
    rc = gate.main(["baseline", "check"])
    out = capsys.readouterr().out
    assert rc == 2
    assert out == "not-json"


def test_main_unknown_command_fallback_branch(monkeypatch) -> None:
    class FakeParser:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def add_subparsers(self, *args: object, **kwargs: object) -> FakeParser:
            return self

        def add_parser(self, *args: object, **kwargs: object) -> FakeParser:
            return self

        def add_argument(self, *args: object, **kwargs: object) -> None:
            return None

        def add_mutually_exclusive_group(self) -> FakeParser:
            return self

        def parse_args(self, argv: list[str] | None = None) -> argparse.Namespace:
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", FakeParser)
    assert gate.main(["ignored"]) == 2


def test_module_main_invocation_executes_system_exit(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sdetkit.gate", "fast", "--list-steps"])
    with pytest.raises(SystemExit) as ex:
        runpy.run_module("sdetkit.gate", run_name="__main__")
    assert ex.value.code == 0
