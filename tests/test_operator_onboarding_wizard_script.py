from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    project_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/operator_onboarding_wizard.py", "--repo-root", str(repo_root), *args],
        cwd=project_root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(project_root / "src")},
    )


def test_operator_onboarding_wizard_reports_ready_with_green_artifacts(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True)
    for name in ("gate-fast.json", "release-preflight.json", "doctor.json"):
        (build / name).write_text(json.dumps({"ok": True, "failed_steps": []}), encoding="utf-8")
    out = tmp_path / "summary.json"
    proc = _run(tmp_path, "--out", str(out), "--format", "json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["overall_ready"] is True
    assert payload["checks"]["gate_fast"]["ok"] is True


def test_operator_onboarding_wizard_reports_not_ready_when_missing_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    proc = _run(tmp_path, "--out", str(out), "--format", "json")
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["overall_ready"] is False
    assert payload["checks"]["gate_fast"]["state"] == "missing"
