from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/golden_path_health.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_golden_path_health_reports_ok_when_all_artifacts_are_ok(tmp_path: Path) -> None:
    gate_fast = tmp_path / "gate-fast.json"
    gate_release = tmp_path / "release-preflight.json"
    doctor = tmp_path / "doctor.json"
    out = tmp_path / "golden-path-health.json"
    for path in (gate_fast, gate_release, doctor):
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")

    proc = _run(
        tmp_path,
        "--gate-fast",
        str(gate_fast),
        "--gate-release",
        str(gate_release),
        "--doctor",
        str(doctor),
        "--out",
        str(out),
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_ok"] is True
    assert payload["checks"]["gate_fast"]["ok"] is True


def test_golden_path_health_reports_failure_when_artifact_missing(tmp_path: Path) -> None:
    out = tmp_path / "golden-path-health.json"
    missing_gate_fast = tmp_path / "missing-gate-fast.json"
    missing_gate_release = tmp_path / "missing-gate-release.json"
    missing_doctor = tmp_path / "missing-doctor.json"
    proc = _run(
        tmp_path,
        "--gate-fast",
        str(missing_gate_fast),
        "--gate-release",
        str(missing_gate_release),
        "--doctor",
        str(missing_doctor),
        "--out",
        str(out),
    )
    assert proc.returncode == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_ok"] is False
    assert payload["checks"]["gate_fast"]["state"] == "missing"
