from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_impact_release_guard_passes_with_release_ready_artifacts(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    _write_json(build / "impact-workflow-run.json", {"ok": True})
    _write_json(build / "impact-next-plan.json", {"status": "ready"})
    _write_json(build / "impact-adaptive-review.json", {"overall_score": 92})
    _write_json(build / "impact-criteria-report.json", {"ok": True})
    _write_json(build / "impact-trend-alert.json", {"ok": True, "streak": "flat"})
    _write_json(
        build / "impact-program-scorecard.json",
        {"overall_score": 90, "step_scores": {"step_1": 90, "step_2": 90, "step_3": 90}},
    )

    out = build / "impact-release-guard.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/impact_release_guard.py",
            "--build-dir",
            str(build),
            "--out",
            str(out),
            "--format",
            "json",
            "--branch",
            "main",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_impact_release_guard_blocks_when_artifacts_missing(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "scripts/impact_release_guard.py", "--build-dir", str(build)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
