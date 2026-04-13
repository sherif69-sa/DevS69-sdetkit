from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/adoption_scorecard.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_adoption_scorecard_reports_excellent_when_all_inputs_ok(tmp_path: Path) -> None:
    golden = tmp_path / "golden.json"
    drift = tmp_path / "drift.json"
    legacy = tmp_path / "legacy.json"
    out = tmp_path / "score.json"
    golden.write_text(
        json.dumps({"overall_ok": True, "checks": {"gate_release": {"ok": True}}}), encoding="utf-8"
    )
    drift.write_text(json.dumps({"overall_ok": True}), encoding="utf-8")
    legacy.write_text(json.dumps({"overall_ok": True}), encoding="utf-8")
    proc = _run(
        "--golden",
        str(golden),
        "--drift",
        str(drift),
        "--legacy",
        str(legacy),
        "--out",
        str(out),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["score"] == 100
    assert payload["band"] == "excellent"


def test_adoption_scorecard_reports_early_when_inputs_missing(tmp_path: Path) -> None:
    out = tmp_path / "score.json"
    proc = _run("--out", str(out), "--format", "json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["score"] == 0
    assert payload["band"] == "early"
