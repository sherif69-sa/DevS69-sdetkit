from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import gate


def _ns_fast(**kwargs):
    base = dict(
        root=".",
        only=None,
        skip=None,
        list_steps=False,
        fix=False,
        fix_only=False,
        no_doctor=True,
        no_ci_templates=True,
        no_ruff=True,
        no_mypy=True,
        no_pytest=True,
        strict=False,
        format="json",
        out=None,
        stable_json=False,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_format_md_failed_steps_section_is_rendered() -> None:
    payload = {
        "ok": False,
        "root": "/tmp/repo",
        "steps": [{"id": "pytest", "ok": False, "rc": 2, "duration_ms": 3}],
        "failed_steps": ["pytest"],
    }

    text = gate._format_md(payload)

    assert "#### Failed steps" in text
    assert "- `pytest`" in text


def test_run_fast_executes_ci_templates_mypy_and_pytest_args(monkeypatch, capsys) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate._run_fast(
        _ns_fast(
            only="ci_templates,mypy,pytest",
            no_ci_templates=False,
            no_mypy=False,
            no_pytest=False,
            mypy_args="src tests",
            pytest_args="tests/test_gate_fast.py -q",
            format="text",
        )
    )

    assert rc == 0
    assert any(
        cmd[:5]
        == [
            gate.sys.executable,
            "-m",
            "sdetkit",
            "ci",
            "validate-templates",
        ]
        for cmd in seen
    )
    assert any(
        cmd[:3] == [gate.sys.executable, "-m", "mypy"] and cmd[-2:] == ["src", "tests"]
        for cmd in seen
    )
    assert any(
        cmd[:3] == [gate.sys.executable, "-m", "pytest"]
        and cmd[-2:] == ["tests/test_gate_fast.py", "-q"]
        for cmd in seen
    )
    assert "gate fast: OK" in capsys.readouterr().out


def test_run_fast_strict_doctor_uses_medium_fail_on(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate._run_fast(_ns_fast(only="doctor", no_doctor=False, strict=True))

    assert rc == 0
    doctor_cmd = seen[0]
    fail_idx = doctor_cmd.index("--fail-on")
    assert doctor_cmd[fail_idx + 1] == "medium"


def test_playbooks_validate_args_aliases_variant() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )

    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]


def test_baseline_check_returns_upstream_failure_without_snapshot_io(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            return 2
        return original_main(args)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--", "--no-doctor", "--no-ci-templates", "--no-mypy"])

    assert rc == 2
    assert not (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").exists()


def test_baseline_check_handles_invalid_current_json_and_invalid_snapshot_json(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{broken\n", encoding="utf-8")

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            print("{not-json")
            return 0
        return original_main(args)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--diff"])

    out = capsys.readouterr().out
    assert rc == 2
    assert out.startswith("{not-json")


def test_baseline_check_diff_context_negative_is_clamped(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    rc_write = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc_write == 0
    capsys.readouterr()

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.write_text("{}\n", encoding="utf-8")

    rc_check = gate.main(
        [
            "baseline",
            "check",
            "--diff",
            "--diff-context",
            "-4",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc_check == 2
    assert payload["snapshot_diff_ok"] is False
    assert payload["snapshot_diff"].startswith("--- snapshot\n+++ current\n")


def test_baseline_check_with_relative_path_writes_under_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "artifacts/snap.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    assert rc == 0
    assert (tmp_path / "artifacts" / "snap.json").exists()


def test_main_unknown_command_fallback(monkeypatch, capsys) -> None:
    class _FakeParser:
        def add_subparsers(self, *args, **kwargs):
            class _FakeSub:
                def add_parser(self, *a, **k):
                    class _P:
                        def add_argument(self, *a2, **k2):
                            return None

                        def add_mutually_exclusive_group(self):
                            class _G:
                                def add_argument(self, *a3, **k3):
                                    return None

                            return _G()

                    return _P()

            return _FakeSub()

        def parse_args(self, args=None):
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", lambda *a, **k: _FakeParser())

    rc = gate.main([])

    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err
