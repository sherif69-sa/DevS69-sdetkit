from __future__ import annotations

import json
import sys
from pathlib import Path

from sdetkit import gate


def test_gate_fast_adoption_profile_runs_basic_doctor_only(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "{}",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--profile", "adoption", "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "fast"
    assert payload["gate_profile"] == "adoption"
    assert payload["failed_steps"] == []
    assert [step["id"] for step in payload["steps"]] == ["doctor"]
    assert calls == [[sys.executable, "-m", "sdetkit", "doctor", "--format", "json"]]


def test_gate_release_adoption_profile_runs_doctor_and_adoption_fast(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "{}",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--profile", "adoption", "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "release"
    assert payload["gate_profile"] == "adoption"
    assert payload["failed_steps"] == []
    assert [step["id"] for step in payload["steps"]] == [
        "doctor_release",
        "gate_fast",
    ]
    assert calls == [
        [sys.executable, "-m", "sdetkit", "doctor", "--format", "json"],
        [
            sys.executable,
            "-m",
            "sdetkit",
            "gate",
            "fast",
            "--root",
            str(tmp_path.resolve()),
            "--profile",
            "adoption",
            "--format",
            "json",
        ],
    ]


def test_gate_fast_strict_default_is_unchanged(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "{}",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_profile"] == "strict"
    assert [step["id"] for step in payload["steps"]] == [
        "doctor",
        "ci_templates",
        "ruff",
        "ruff_format",
        "mypy",
        "pytest",
    ]
