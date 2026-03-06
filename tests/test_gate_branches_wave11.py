from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

import pytest
from pathlib import Path
from types import SimpleNamespace

from sdetkit import gate


def _ns(**kwargs):
    base = dict(
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


def test_format_md_failed_steps_section() -> None:
    payload = {
        "ok": False,
        "root": "/repo",
        "steps": [{"id": "x", "ok": False, "rc": 1, "duration_ms": 3}],
        "failed_steps": ["x", "y"],
    }
    out = gate._format_md(payload)
    assert "#### Failed steps" in out
    assert "- `x`" in out
    assert "- `y`" in out


def test_run_fast_strict_doctor_and_ci_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path):
def test_format_md_includes_failed_steps_section() -> None:
    out = gate._format_md(
        {
            "ok": False,
            "root": "/tmp/repo",
            "steps": [{"id": "ruff", "ok": True, "rc": 0, "duration_ms": 1}],
            "failed_steps": ["doctor", "pytest"],
        }
    )
    assert "#### Failed steps" in out
    assert "- `doctor`" in out
    assert "- `pytest`" in out


def test_run_fast_covers_strict_ci_mypy_and_pytest_arg_splitting(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(
            strict=True,
            no_ruff=True,
            no_mypy=True,
            no_pytest=True,
            format="json",
        )
    )
    assert rc == 0
    joined = [" ".join(c) for c in calls]
    assert any(
        "doctor --dev --ci --deps --clean-tree --repo --fail-on medium --format json" in x
        for x in joined
    )
    assert any("ci validate-templates --root" in x for x in joined)


def test_run_fast_mypy_and_pytest_arg_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path):
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(
            no_doctor=True,
            no_ci_templates=True,
            no_ruff=True,
            mypy_args="src tests",
            pytest_args="-q tests/test_gate_fast.py",
            format="text",
        )
    )
    assert rc == 0

    mypy_call = [c for c in calls if len(c) >= 3 and c[2] == "mypy"][0]
    pytest_call = [c for c in calls if len(c) >= 3 and c[2] == "pytest"][0]
    assert mypy_call[-2:] == ["src", "tests"]
    assert pytest_call[-2:] == ["-q", "tests/test_gate_fast.py"]


def test_run_fast_failure_reports_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path):
        if "mypy" in cmd:
            return {
                "cmd": cmd,
                "rc": 1,
                "ok": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "bad",
            }
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(no_doctor=True, no_ci_templates=True, no_ruff=True, no_pytest=True, format="text")
    )
    assert rc == 2
    assert "gate: problems found" in capsys.readouterr().err


def test_baseline_relative_path_is_anchored_and_write_then_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )

    rc_write = gate.main(
        ["baseline", "write", "--path", "snaps/current.json", "--", "--only", "ruff"]
    )
    assert rc_write == 0
    assert (tmp_path / "snaps" / "current.json").exists()

    rc_check = gate.main(
        ["baseline", "check", "--path", "snaps/current.json", "--", "--only", "ruff"]
    )
    assert rc_check == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["snapshot_diff_ok"] is True


def test_baseline_propagates_nonzero_fast_rc(capsys: pytest.CaptureFixture[str]) -> None:
    rc = gate.main(["baseline", "check", "--", "--only", "no-such-step"])
    assert rc == 2
    assert "unknown step id" in capsys.readouterr().err


def test_baseline_handles_non_json_current_and_snapshot_diff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]

    rc = gate.main(
        [
            "fast",
            "--root",
            str(tmp_path),
            "--only",
            "doctor,ci_templates,mypy,pytest",
            "--strict",
            "--mypy-args",
            "src tests",
            "--pytest-args",
            "-q tests/test_gate_branches_wave11.py",
            "--format",
            "text",
        ]
    )

    assert rc == 0
    # doctor uses medium fail-on in strict mode
    doctor_cmd = next(cmd for cmd in calls if "doctor" in cmd)
    assert "--fail-on" in doctor_cmd
    assert doctor_cmd[doctor_cmd.index("--fail-on") + 1] == "medium"

    ci_cmd = next(cmd for cmd in calls if "validate-templates" in cmd)
    assert "--strict" in ci_cmd

    mypy_cmd = next(cmd for cmd in calls if "mypy" in cmd)
    assert mypy_cmd[-2:] == ["src", "tests"]

    pytest_cmd = next(cmd for cmd in calls if "pytest" in cmd)
    assert pytest_cmd[-2:] == ["-q", "tests/test_gate_branches_wave11.py"]


def test_playbooks_validate_args_aliases_branch() -> None:
    ns = SimpleNamespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )
    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]


def test_baseline_uses_relative_custom_snapshot_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snapshots/custom-fast.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )
    assert rc == 0
    assert (tmp_path / "snapshots" / "custom-fast.json").exists()


def test_baseline_check_returns_fast_rc_when_nested_gate_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["baseline", "check", "--", "--only", "not-a-step"])
    assert rc == 2


def test_baseline_check_handles_non_json_nested_output_with_diff(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("<<<not-json-snapshot>>>", encoding="utf-8")

    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )

    original_write_output = gate._write_output

    def fake_write_output(text: str, out: str | None) -> None:
        # Force recursive `baseline -> fast` call to produce invalid JSON text.
        if out is None and text.lstrip().startswith("{"):
            import sys

            sys.stdout.write("<<<not-json-current>>>")
            return
        original_write_output(text, out)

    monkeypatch.setattr(gate, "_write_output", fake_write_output)

    rc = gate.main(["baseline", "check", "--diff"])
    assert rc == 2
    out = capsys.readouterr().out
    assert out == "<<<not-json-current>>>"


def test_baseline_diff_context_negative_is_clamped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )

    # Write a baseline for one selection.
    assert gate.main(["baseline", "write", "--", "--only", "ruff"]) == 0
    # Check with different selection to trigger drift and exercise negative context path.
    rc = gate.main(["baseline", "check", "--diff", "--diff-context", "-5", "--", "--only", "mypy"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["snapshot_diff_ok"] is False
    assert "snapshot drift detected" in payload["snapshot_diff_summary"]
    assert isinstance(payload.get("snapshot_diff", ""), str)


def test_baseline_missing_snapshot_annotates_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )
    rc = gate.main(["baseline", "check"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["snapshot_diff_ok"] is False
    assert "snapshot file missing" in payload["snapshot_diff_summary"]


def test_main_unknown_command_branch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self, args=None: argparse.Namespace(cmd="nope"),
    )
    rc = gate.main([])
    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err


def test_module_main_guard_executes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["sdetkit.gate", "fast", "--list-steps"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_module("sdetkit.gate", run_name="__main__")
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "ruff" in out and "pytest" in out


def test_release_failure_emits_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path):
        if "playbooks" in cmd:
            return {"cmd": cmd, "rc": 2, "ok": False, "duration_ms": 1, "stdout": "", "stderr": ""}
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate.main(["release", "--format", "json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "playbooks_validate" in payload["failed_steps"]


@pytest.mark.parametrize(
    ("ns_kwargs", "expected_prefix"),
    [
        (
            {
                "playbooks_all": True,
                "playbooks_legacy": False,
                "playbooks_aliases": False,
                "playbook_name": [],
            },
            ["--all"],
        ),
        (
            {
                "playbooks_all": False,
                "playbooks_legacy": True,
                "playbooks_aliases": False,
                "playbook_name": [],
            },
            ["--legacy"],
        ),
        (
            {
                "playbooks_all": False,
                "playbooks_legacy": False,
                "playbooks_aliases": True,
                "playbook_name": [],
            },
            ["--aliases"],
        ),
        (
            {
                "playbooks_all": False,
                "playbooks_legacy": False,
                "playbooks_aliases": False,
                "playbook_name": [],
            },
            ["--recommended"],
        ),
    ],
)
def test_playbooks_validate_modes(ns_kwargs: dict[str, object], expected_prefix: list[str]) -> None:
    ns = argparse.Namespace(**ns_kwargs)
    args = gate._playbooks_validate_args(ns)
    assert args[:1] == expected_prefix
    assert args[-2:] == ["--format", "json"]
    snap.write_text("old", encoding="utf-8")

    real_main = gate.main

    def patched_main(argv: list[str] | None = None) -> int:
        if argv and argv[0] != "baseline":
            print("new", end="")
            return 0
        return real_main(argv)

    monkeypatch.setattr(gate, "main", patched_main)
    rc = real_main(["baseline", "check", "--diff", "--diff-context", "0"])

    out = capsys.readouterr().out
    assert rc == 2
    # Non-JSON nested gate output is passed through as-is for baseline check output.
    assert out == "new"


def test_gate_main_unknown_command_branch(monkeypatch) -> None:
    class DummyParser:
        def add_subparsers(self, **kwargs):
            class DummySubparsers:
                def add_parser(self, _name):
                    class DummyAdd:
                        def add_argument(self, *args, **kwargs):
                            return None

                        def add_mutually_exclusive_group(self):
                            return self

                    return DummyAdd()

            return DummySubparsers()

        def parse_args(self, argv):
            return SimpleNamespace(cmd="unexpected")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", lambda *a, **k: DummyParser())
    rc = gate.main(["ignored"])
    assert rc == 2
