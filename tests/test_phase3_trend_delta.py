from __future__ import annotations

import json
from pathlib import Path

from scripts import build_phase3_trend_delta as trend_script
from scripts import phase3_quality_engine as q


def _summary(path: Path, checks: list[dict[str, object]]) -> Path:
    payload = {"schema_version": "sdetkit.phase1_baseline.v1", "checks": checks}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_trend_delta_bootstrap_without_previous(tmp_path: Path) -> None:
    current = _summary(tmp_path / "current.json", [{"id": "doctor", "ok": False, "rc": 1}])
    out = tmp_path / "out.json"

    rc = trend_script.main(["--current", str(current), "--out-json", str(out), "--skip-md", "--format", "json"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == q.TREND_SCHEMA_VERSION
    assert payload["status"] == "bootstrap"


def test_trend_delta_regression_classification(tmp_path: Path) -> None:
    previous = _summary(tmp_path / "prev.json", [{"id": "doctor", "ok": True, "rc": 0}])
    current = _summary(tmp_path / "cur.json", [{"id": "doctor", "ok": False, "rc": 1}])
    out = tmp_path / "out.json"

    rc = trend_script.main(
        [
            "--current",
            str(current),
            "--previous",
            str(previous),
            "--out-json",
            str(out),
            "--skip-md",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "worsening"
    assert payload["regressions"] == ["doctor"]


def test_trend_delta_auto_uses_history_when_previous_not_passed(tmp_path: Path) -> None:
    current = _summary(tmp_path / "phase1-baseline-summary.json", [{"id": "doctor", "ok": False, "rc": 1}])
    _summary(tmp_path / "history" / "phase1-baseline-summary-old.json", [{"id": "doctor", "ok": True, "rc": 0}])
    out = tmp_path / "out.json"

    rc = trend_script.main(["--current", str(current), "--out-json", str(out), "--skip-md", "--format", "json"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "worsening"
