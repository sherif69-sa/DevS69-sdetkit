from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from sdetkit import gate


def _ok_result(cmd: list[str]) -> dict[str, object]:
    return {
        "cmd": cmd,
        "rc": 0,
        "ok": True,
        "duration_ms": 1,
        "stdout": "",
        "stderr": "",
    }


def test_format_md_includes_failed_steps_section() -> None:
    payload = {
        "ok": False,
        "root": "/repo",
        "steps": [{"id": "ruff", "ok": False, "rc": 1, "duration_ms": 2}],
        "failed_steps": ["ruff"],
    }

    out = gate._format_md(payload)

    assert "#### Failed steps" in out
    assert "- `ruff`" in out


def test_run_fast_strict_sets_doctor_fail_on_medium(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        [
            "fast",
            "--strict",
            "--format",
            "json",
            "--only",
            "doctor",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert calls[0][3:] == [
        "doctor",
        "--dev",
        "--ci",
        "--deps",
        "--clean-tree",
        "--repo",
        "--fail-on",
        "medium",
        "--format",
        "json",
    ]


def test_run_fast_runs_ci_templates_step(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        [
            "fast",
            "--format",
            "json",
            "--only",
            "ci_templates",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["ci_templates"]
    assert calls[0][3:] == [
        "ci",
        "validate-templates",
        "--root",
        str(Path(".").resolve()),
        "--format",
        "json",
        "--strict",
    ]


def test_run_fast_uses_custom_mypy_and_pytest_args(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        [
            "fast",
            "--format",
            "text",
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--mypy-args",
            "src tests",
            "--pytest-args",
            "-q tests/test_gate_coverage_wave11.py",
        ]
    )

    assert rc == 0
    _ = capsys.readouterr().out
    assert calls[0][2:] == ["mypy", "src", "tests"]
    assert calls[1][2:] == ["pytest", "-q", "tests/test_gate_coverage_wave11.py"]


def test_playbooks_validate_args_aliases_path() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )

    args = gate._playbooks_validate_args(ns)

    assert args == ["--aliases", "--format", "json"]


def test_baseline_uses_relative_snapshot_path_and_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snapshots/gate.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    assert rc == 0
    assert (tmp_path / "snapshots" / "gate.json").exists()


def test_baseline_propagates_nonzero_fast_rc(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    rc = gate.main(["baseline", "check", "--", "--only", "nope"])

    assert rc == 2
    assert capsys.readouterr().out == ""


def test_baseline_handles_non_json_current_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fast(ns: argparse.Namespace) -> int:
        print("not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--diff", "--", "--no-doctor"])

    assert rc == 2
    assert capsys.readouterr().out == "not-json\n"


def test_baseline_diff_keeps_invalid_snapshot_and_current_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("old-snapshot", encoding="utf-8")

    def fake_fast(ns: argparse.Namespace) -> int:
        print("new-current", end="")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--diff", "--", "--no-doctor"])

    assert rc == 2
    assert capsys.readouterr().out == "new-current"


def test_baseline_when_current_json_decode_fails_keeps_raw_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{}\n", encoding="utf-8")

    def fake_fast(ns: argparse.Namespace) -> int:
        print("still-not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--", "--no-doctor"])

    assert rc == 2


def test_main_unknown_gate_command_branch(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    class FakeParser:
        def __init__(self, *args, **kwargs):
            pass

        def add_subparsers(self, **kwargs):
            class FakeSub:
                def add_parser(self, *a, **k):
                    class FakeCmd:
                        def add_argument(self, *args, **kwargs):
                            return None

                        def add_mutually_exclusive_group(self):
                            class FakeGroup:
                                def add_argument(self, *args, **kwargs):
                                    return None

                            return FakeGroup()

                    return FakeCmd()

            return FakeSub()

        def parse_args(self, *_args, **_kwargs):
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", FakeParser)

    rc = gate.main(["does-not-matter"])

    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err
