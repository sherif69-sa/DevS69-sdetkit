from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_gate_trend_text_output(tmp_path: Path, capsys) -> None:
    baseline = _write(tmp_path / "baseline.json", {"ok": False, "failed_steps": ["ruff", "mypy"]})
    current = _write(tmp_path / "current.json", {"ok": True, "failed_steps": ["mypy"]})

    rc = gate.main(["trend", "--baseline", str(baseline), "--current", str(current)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "gate trend" in out
    assert "status_delta=improved" in out
    assert "baseline=2 current=1 delta=-1" in out


def test_gate_trend_json_output(tmp_path: Path, capsys) -> None:
    baseline = _write(tmp_path / "baseline.json", {"ok": True, "failed_steps": []})
    current = _write(tmp_path / "current.json", {"ok": False, "failed_steps": ["pytest"]})

    rc = gate.main(
        [
            "trend",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status_delta"] == "regressed"
    assert payload["failed_steps_delta"] == 1
    assert payload["baseline_ok"] is True
    assert payload["current_ok"] is False
