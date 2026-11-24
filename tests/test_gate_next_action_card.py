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
        "recommendations": ["python -m mypy src"],
        "steps": [{"id": "mypy", "ok": False, "rc": 1, "stdout": "", "stderr": ""}],
    }

    card = gate._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "unknown"
    assert card["first_failure"] == "mypy"
    assert card["affected_file"] == ""
    assert card["next_command"] == "python -m mypy src"
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


def test_gate_fast_json_includes_next_action_card(monkeypatch, tmp_path: Path, capsys) -> None:
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
    (tmp_path / "tests").mkdir()
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


def test_gate_fast_text_includes_next_action_card(monkeypatch, tmp_path: Path, capsys) -> None:
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
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "text", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 2
    text = capsys.readouterr().out
    assert text.startswith("SDETKit gate fast: NO_SHIP\n")
    # The file is in the failure already, so the line does not repeat it.
    assert "first failure (test): FAILED tests/test_release_contract.py::test_wheel_smoke\n" in text
    assert "next: cd " in text
    assert " -m pytest -q tests/test_release_contract.py::test_wheel_smoke" in text


def test_followup_retains_external_root_and_check_interpreter(tmp_path: Path) -> None:
    import subprocess
    import sys

    root = tmp_path / "repo with spaces"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests/test_calc.py").write_text("def test_add():\n    assert 2 + 3 == 6\n")
    payload = {
        "root": str(root),
        "environment": {"python": sys.executable},
        "profile": "fast",
        "ok": False,
        "failed_steps": ["pytest"],
        "steps": [
            {
                "id": "pytest",
                "ok": False,
                "rc": 1,
                "stdout": "FAILED tests/test_calc.py::test_add - assert 5 == 6",
                "stderr": "",
            }
        ],
    }
    card = gate._next_action_card(payload)
    result = subprocess.run(
        ["sh", "-c", card["next_command"]], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAILED tests/test_calc.py::test_add" in result.stdout
    assert "file or directory not found" not in result.stderr
    assert sys.executable in card["next_command"]
    assert card["classification"] == "test"


def test_gate_external_repo_next_command_replays_actual_failure(tmp_path: Path) -> None:
    import subprocess
    import sys

    root = tmp_path / "external repo"
    root.mkdir()
    (root / "tests").mkdir()
    (root / "tests/test_arithmetic.py").write_text("def test_total():\n    assert 2 + 3 == 6\n")
    report = tmp_path / "gate.json"
    rc = gate.main(
        [
            "fast",
            "--root",
            str(root),
            "--only",
            "pytest",
            "--python",
            sys.executable,
            "--format",
            "json",
            "--out",
            str(report),
        ]
    )
    assert rc == 2
    payload = json.loads(report.read_text())
    assert payload["verdict"]["decision"] == "NO_SHIP"
    replay = subprocess.run(
        ["sh", "-c", payload["next_action"]["next_command"]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert replay.returncode == 1, replay.stdout + replay.stderr
    assert "FAILED tests/test_arithmetic.py::test_total" in replay.stdout
    assert "file or directory not found" not in replay.stderr
