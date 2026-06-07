from __future__ import annotations

import json
from pathlib import Path

from scripts import phase_sequential_executor as pse


def test_build_payload_uses_current_phase() -> None:
    payload = pse.build_payload(Path("plans/strategic-execution-model-2026.json"))
    assert payload["ok"] is True
    assert payload["current_phase"]["id"] == 1
    assert payload["next_commands"]
    assert "progress" in payload


def test_main_json_output(capsys) -> None:
    rc = pse.main(["--format", "json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema_version"] == "sdetkit.phase_sequential_executor.v1"


def test_missing_plan_returns_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    payload = pse.build_payload(missing)
    assert payload["ok"] is False


def test_progress_from_status_file(tmp_path: Path) -> None:
    status = tmp_path / "phase1-status.json"
    status.write_text(
        json.dumps(
            {
                "ok": False,
                "accomplished": ["a", "b", "c"],
                "not_yet": ["d"],
                "hard_blockers": ["d"],
            }
        ),
        encoding="utf-8",
    )
    payload = pse.build_payload(
        Path("plans/strategic-execution-model-2026.json"),
        status_path=status,
    )
    assert payload["progress"]["available"] is True
    assert payload["progress"]["progress_percent"] == 75.0
