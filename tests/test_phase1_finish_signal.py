from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_finish_signal as signal


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_finish_signal_near_finish() -> None:
    out = signal.build_finish_signal(
        {"completion_percent": 80},
        {
            "ready_to_close": False,
            "completion_gate": {"ok": False, "failing_required_checks": ["doctor"]},
        },
    )
    assert out["status"] == "near_finish"


def test_main_missing_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = signal.main(["--format", "json"])
    assert rc == 1


def test_main_success(tmp_path: Path) -> None:
    control = tmp_path / "control.json"
    dash = tmp_path / "dash.json"
    _write(control, {"completion_percent": 100})
    _write(
        dash,
        {
            "ready_to_close": True,
            "completion_gate": {"ok": True},
            "next_step": "make phase1-closeout",
        },
    )
    rc = signal.main(["--control-loop", str(control), "--dashboard", str(dash), "--format", "json"])
    assert rc == 0
