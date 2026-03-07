from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from sdetkit import gate


def _ns(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "root": ".",
        "only": None,
        "skip": None,
        "list_steps": False,
        "fix": False,
        "fix_only": False,
        "no_doctor": False,
        "no_ci_templates": False,
        "no_ruff": False,
        "no_mypy": False,
        "no_pytest": False,
        "strict": False,
        "format": "text",
        "out": None,
        "mypy_args": None,
        "full_pytest": False,
        "pytest_args": None,
        "stable_json": False,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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
    joined = [" ".join(c) for c in calls]
    assert any(
        "doctor --dev --ci --deps --clean-tree --repo --fail-on medium --format json" in x
        for x in joined
    )
    assert any("ci validate-templates --root" in x and "--strict" in x for x in joined)
    assert any(
        c[:4] == [gate.sys.executable, "-m", "mypy", "src"] and c[-1] == "tests" for c in calls
    )
    assert any(
        c[:4] == [gate.sys.executable, "-m", "pytest", "-q"]
        and c[-1] == "tests/test_gate_branches_wave11.py"
        for c in calls
    )


def test_run_fast_failure_reports_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        is_mypy = cmd[:3] == [gate.sys.executable, "-m", "mypy"]
        return {
            "cmd": cmd,
            "rc": 1 if is_mypy else 0,
            "ok": not is_mypy,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "bad",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(no_doctor=True, no_ci_templates=True, no_ruff=True, no_pytest=True, format="text")
    )
    assert rc == 2
    assert "gate: problems found" in capsys.readouterr().err


def test_baseline_relative_path_write_then_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

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
