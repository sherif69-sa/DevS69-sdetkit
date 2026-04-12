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
        "code_scanning",
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
    assert "duration_ms" not in payload["steps"][0]
    assert "stdout" not in payload["steps"][0]
    assert "stderr" not in payload["steps"][0]
    assert [step["id"] for step in payload["steps"]] == [
        "doctor_release",
        "code_scanning",
        "playbooks_validate",
        "gate_fast",
    ]
    assert calls[0][3:] == ["doctor", "--release-full", "--format", "json"]
    assert calls[1][3:5] == ["security", "scan"]
    assert calls[2][3:] == ["playbooks", "validate", "--recommended", "--format", "json"]
    assert calls[3][3:6] == ["gate", "fast", "--root"]


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
    assert calls[2][3:] == ["playbooks", "validate", "--legacy", "--format", "json"]


def test_gate_release_passes_playbooks_all_selection(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", "json", "--playbooks-all"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[2][3:] == ["playbooks", "validate", "--all", "--format", "json"]


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
            "weekly-review-lane",
            "--playbook-name",
            "legacy-phase1-hardening",
        ]
    )
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[2][3:] == [
        "playbooks",
        "validate",
        "--name",
        "weekly-review-lane",
        "--name",
        "legacy-phase1-hardening",
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


def test_gate_release_adds_recommendation_for_failed_step(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        is_scan = cmd[3:5] == ["security", "scan"]
        return {
            "cmd": cmd,
            "rc": 1 if is_scan else 0,
            "ok": not is_scan,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "failed",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", "json"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed_steps"] == ["code_scanning"]
    assert payload["recommendations"] == [
        "Inspect security scanning output: python -m sdetkit security scan --format sarif --output build/code-scanning.sarif --fail-on high."
    ]


def test_gate_release_carries_request_context_and_ai_handoff(tmp_path: Path, capsys) -> None:
    rc = gate.main(
        [
            "release",
            "--dry-run",
            "--format",
            "json",
            "--work-id",
            "PR-717",
            "--work-context",
            "owner=platform",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["request_context"]["work_id"] == "PR-717"
    assert payload["request_context"]["work_context"]["owner"] == "platform"
    assert "recommended_review_command" in payload["ai_assistance"]


def test_gate_release_fails_when_no_checks_are_enabled(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "_release_commands", lambda ns, root: [])

    rc = gate.main(["release", "--format", "json"])
    assert rc == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failed_steps"] == ["configuration"]
    assert payload["steps"] == []
    assert payload["recommendations"][0].startswith("No release checks are enabled.")
