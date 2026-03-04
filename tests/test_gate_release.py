from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def test_gate_release_dry_run_lists_steps(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["release", "--dry-run", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["root"] == "<repo>"
    assert [step["id"] for step in payload["steps"]] == [
        "doctor_release",
        "playbooks_validate",
        "gate_fast",
    ]


def test_gate_release_runs_expected_commands(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", "json", "--release-full"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert [step["id"] for step in payload["steps"]] == [
        "doctor_release",
        "playbooks_validate",
        "gate_fast",
    ]
    assert calls[0][3:] == ["doctor", "--release-full", "--format", "json"]
    assert calls[1][3:] == ["playbooks", "validate", "--recommended", "--format", "json"]
    assert calls[2][3:6] == ["gate", "fast", "--root"]


def test_gate_release_passes_playbook_selection_flags(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", "json", "--playbooks-legacy"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[1][3:] == ["playbooks", "validate", "--legacy", "--format", "json"]


def test_gate_release_passes_named_playbooks(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "release",
            "--format",
            "json",
            "--playbook-name",
            "day28-weekly-review",
            "--playbook-name",
            "day29-phase1-hardening",
        ]
    )
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[1][3:] == [
        "playbooks",
        "validate",
        "--name",
        "day28-weekly-review",
        "--name",
        "day29-phase1-hardening",
        "--format",
        "json",
    ]


def test_gate_release_dry_run_normalizes_commands(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["release", "--dry-run", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    cmds = [step["cmd"] for step in payload["steps"]]
    assert all(cmd[0] == "python" for cmd in cmds)
    assert any("<repo>" in tok for tok in cmds[-1])
