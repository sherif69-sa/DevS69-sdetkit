from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sdetkit import gate


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
