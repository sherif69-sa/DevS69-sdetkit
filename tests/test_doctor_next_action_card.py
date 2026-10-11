from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_next_action_card_for_failed_check() -> None:
    payload = {
        "ok": False,
        "failed_checks": ["pyproject"],
        "next_actions": [
            {
                "id": "pyproject",
                "severity": "high",
                "summary": "pyproject.toml is missing",
                "fix": ["Fix pyproject.toml syntax."],
            }
        ],
        "checks": {
            "pyproject": {
                "ok": False,
                "severity": "high",
                "summary": "pyproject.toml is missing",
                "evidence": [
                    {
                        "type": "parse",
                        "message": "pyproject.toml is missing",
                        "path": "pyproject.toml",
                    }
                ],
                "fix": ["Fix pyproject.toml syntax."],
            }
        },
    }

    card = doctor._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "pyproject"
    assert card["first_failure"] == "pyproject.toml is missing"
    assert card["affected_file"] == "pyproject.toml"
    assert card["next_command"] == "Fix pyproject.toml syntax."
    assert card["authority"] == "review-first"


def test_doctor_next_action_card_prefers_severity_ranked_next_action() -> None:
    payload = {
        "ok": False,
        "failed_checks": ["ascii", "pyproject"],
        "next_actions": [
            {
                "id": "pyproject",
                "severity": "high",
                "summary": "pyproject.toml is missing",
                "fix": ["Fix pyproject.toml syntax."],
            },
            {
                "id": "ascii",
                "severity": "medium",
                "summary": "non-ascii characters found",
                "fix": ["Replace non-ascii characters."],
            },
        ],
        "checks": {
            "ascii": {
                "ok": False,
                "severity": "medium",
                "summary": "non-ascii characters found",
                "evidence": [
                    {"type": "ascii", "message": "non-ascii characters found", "path": "src/app.py"}
                ],
                "fix": ["Replace non-ascii characters."],
            },
            "pyproject": {
                "ok": False,
                "severity": "high",
                "summary": "pyproject.toml is missing",
                "evidence": [
                    {
                        "type": "parse",
                        "message": "pyproject.toml is missing",
                        "path": "pyproject.toml",
                    }
                ],
                "fix": ["Fix pyproject.toml syntax."],
            },
        },
    }

    card = doctor._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "pyproject"
    assert card["first_failure"] == "pyproject.toml is missing"
    assert card["affected_file"] == "pyproject.toml"
    assert card["next_command"] == "Fix pyproject.toml syntax."
    assert card["authority"] == "review-first"


def test_doctor_next_action_card_fails_closed_without_evidence() -> None:
    payload = {
        "ok": False,
        "failed_checks": ["deps"],
        "next_actions": [
            {
                "id": "deps",
                "severity": "medium",
                "summary": "dependency consistency check failed",
                "fix": [],
            }
        ],
        "checks": {
            "deps": {
                "ok": False,
                "severity": "medium",
                "summary": "dependency consistency check failed",
                "evidence": [],
                "fix": [],
            }
        },
    }

    card = doctor._next_action_card(payload)

    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "unknown"
    assert card["first_failure"] == "deps"
    assert card["affected_file"] == ""
    assert card["next_command"] == "python -m sdetkit doctor --format json --out build/doctor.json"
    assert card["authority"] == "review-first"


def test_doctor_next_action_card_for_passing_doctor_does_not_claim_ship() -> None:
    payload = {
        "ok": True,
        "failed_checks": [],
        "next_actions": [],
        "checks": {
            "pyproject": {
                "ok": True,
                "severity": "medium",
                "summary": "pyproject.toml is valid TOML",
                "evidence": [],
                "fix": [],
            }
        },
    }

    card = doctor._next_action_card(payload)

    assert card["decision"] == "CONTINUE"
    assert card["classification"] == ""
    assert card["first_failure"] == ""
    assert card["affected_file"] == ""
    assert card["next_command"] == ""
    assert card["authority"] == "review-first"


def test_doctor_json_includes_next_action_card(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--only", "pyproject", "--format", "json", "--no-workspace"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    card = payload["next_action"]
    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "pyproject"
    assert card["affected_file"] == "pyproject.toml"
    assert card["authority"] == "review-first"


def test_doctor_json_passing_run_includes_continue_card(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--only", "pyproject", "--format", "json", "--no-workspace"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    card = payload["next_action"]
    assert card["decision"] == "CONTINUE"
    assert card["classification"] == ""
    assert card["first_failure"] == ""
    assert card["affected_file"] == ""
    assert card["next_command"] == ""
    assert card["authority"] == "review-first"


def test_doctor_text_includes_next_action_card(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--only", "pyproject", "--format", "text", "--no-workspace"])
    assert rc == 2
    text = capsys.readouterr().out
    assert "decision: NO-SHIP" in text
    assert "affected_file: pyproject.toml" in text
    assert "authority: review-first" in text


def test_doctor_md_includes_next_action_card(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--only", "pyproject", "--format", "md", "--no-workspace"])
    assert rc == 2
    text = capsys.readouterr().out
    assert "#### Next action" in text
    assert "decision: `NO-SHIP`" in text
    assert "authority: `review-first`" in text
