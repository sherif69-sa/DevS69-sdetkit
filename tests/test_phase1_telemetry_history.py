from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_telemetry_history as telemetry


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_history_entry() -> None:
    entry = telemetry.build_history_entry(
        {
            "ok": False,
            "steps": [
                {"command": "make phase1-baseline", "ok": False, "duration_ms": 12},
                {"command": "make phase1-status", "ok": True, "duration_ms": 8},
            ],
        }
    )
    assert entry["duration_ms"] == 20
    assert entry["blocker_categories"] == ["build"]


def test_main_updates_history(tmp_path: Path) -> None:
    run = tmp_path / "run.json"
    history = tmp_path / "history.json"
    summary = tmp_path / "summary.json"

    _write(run, {"ok": True, "steps": [{"command": "make x", "ok": True, "duration_ms": 10}]})

    rc = telemetry.main(
        [
            "--run-json",
            str(run),
            "--history-json",
            str(history),
            "--summary-json",
            str(summary),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert history.exists()
    assert summary.exists()
