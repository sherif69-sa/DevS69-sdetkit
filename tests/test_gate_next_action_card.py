from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def test_gate_next_action_card_for_pytest_failure() -> None:
    payload = {
        "profile": "fast",
        "ok": False,
        "failed_steps": ["pytest"],
        "recommendations": [
            "Inspect doctor evidence first: python -m sdetkit doctor --format json --out build/doctor.json."
        ],
        "steps": [
            {
                "id": "pytest",
                "ok": False,
                "rc": 1,
                "stdout": "FAILED tests/test_release_contract.py::test_wheel_smoke\n",
                "stderr": "",
            }
        ],
    }

    card = gate._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "test"
    assert card["first_failure"] == "FAILED tests/test_release_contract.py::test_wheel_smoke"
    assert card["affected_file"] == "tests/test_release_contract.py"
    assert "pytest" in card["next_command"]
    assert "tests/test_release_contract.py" in card["next_command"]
    assert card["authority"] == "review-first"


def test_gate_next_action_card_fails_closed_without_log_evidence() -> None:
    payload = {
        "profile": "fast",
        "ok": False,
        "failed_steps": ["mypy"],
        "recommendations": [
            "Mypy is missing in this environment. Install dev tooling: python -m pip install -e .[dev,test]."
        ],
        "steps": [{"id": "mypy", "ok": False, "rc": 1, "stdout": "", "stderr": ""}],
    }

    card = gate._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "unknown"
    assert card["first_failure"] == "mypy"
    assert card["affected_file"] == ""
    assert card["next_command"].startswith("Mypy is missing")
    assert card["authority"] == "review-first"


def test_gate_next_action_card_for_passing_fast_gate_does_not_claim_ship() -> None:
    payload = {
        "profile": "fast",
        "ok": True,
        "failed_steps": [],
        "steps": [{"id": "ruff", "ok": True, "rc": 0, "stdout": "", "stderr": ""}],
    }

    card = gate._next_action_card(payload)

    assert card["decision"] == "CONTINUE"
    assert card["classification"] == ""
    assert card["first_failure"] == ""
    assert card["affected_file"] == ""
    assert card["next_command"] == (
        "python -m sdetkit gate release --format json --out build/release-preflight.json"
    )
    assert card["authority"] == "review-first"


def test_gate_next_action_card_for_passing_release_gate_points_to_doctor() -> None:
    payload = {
        "profile": "release",
        "ok": True,
        "failed_steps": [],
        "steps": [],
    }

    card = gate._next_action_card(payload)

    assert card["decision"] == "CONTINUE"
    assert card["next_command"] == "python -m sdetkit doctor --format json --out build/doctor.json"
    assert card["authority"] == "review-first"


def test_gate_fast_json_includes_next_action_card(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {
            "cmd": cmd,
            "rc": 1,
            "ok": False,
            "duration_ms": 1,
            "stdout": "FAILED tests/test_release_contract.py::test_wheel_smoke\n",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "json", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    card = payload["next_action"]
    assert card["decision"] == "NO-SHIP"
    assert card["affected_file"] == "tests/test_release_contract.py"
    assert card["authority"] == "review-first"


def test_gate_fast_text_includes_next_action_card(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {
            "cmd": cmd,
            "rc": 1,
            "ok": False,
            "duration_ms": 1,
            "stdout": "FAILED tests/test_release_contract.py::test_wheel_smoke\n",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "text", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 2
    text = capsys.readouterr().out
    assert "decision: NO-SHIP" in text
    assert "affected_file: tests/test_release_contract.py" in text
    assert "authority: review-first" in text
