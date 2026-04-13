from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, str(root / "scripts/legacy_burndown.py"), *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_legacy_burndown_emits_contract_and_markdown(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    baseline = tmp_path / "baseline.json"
    out_json = tmp_path / "burndown.json"
    out_md = tmp_path / "burndown.md"
    out_csv = tmp_path / "burndown.csv"

    current.write_text(
        json.dumps(
            {
                "count": 2,
                "findings": [
                    {"path": "docs/index.md", "command": "phase1-hardening"},
                    {"path": "scripts/ci.sh", "command": "weekly-review-lane"},
                ],
            }
        ),
        encoding="utf-8",
    )
    baseline.write_text(
        json.dumps(
            {
                "count": 5,
                "findings": [
                    {"path": "docs/index.md", "command": "phase1-hardening"},
                    {"path": "docs/guide.md", "command": "phase1-hardening"},
                    {"path": "scripts/ci.sh", "command": "weekly-review-lane"},
                    {"path": "src/sdetkit/legacy.py", "command": "phase2-kickoff"},
                    {"path": "tests/test_legacy.py", "command": "phase3-preplan-closeout"},
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        "--current",
        str(current),
        "--baseline",
        str(baseline),
        "--target-reduction-pct",
        "40",
        "--json-out",
        str(out_json),
        "--md-out",
        str(out_md),
        "--csv-out",
        str(out_csv),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "1"
    assert payload["totals"] == {"baseline": 5, "current": 2, "delta": -3, "reduction_pct": 60.0}
    assert payload["weekly_kpi"]["target_met"] is True
    assert payload["groups"]["current"]["domain"]["docs"] == 1
    assert payload["groups"]["current"]["category"]["phase1"] == 1
    assert out_md.exists()
    summary = out_md.read_text(encoding="utf-8")
    assert "# Legacy burn-down weekly summary" in summary
    csv = out_csv.read_text(encoding="utf-8")
    assert "metric,value" in csv
    assert "target_met,true" in csv


def test_legacy_burndown_defaults_baseline_to_current(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    current.write_text(json.dumps({"count": 3, "findings": []}), encoding="utf-8")
    proc = _run("--current", str(current), "--format", "json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["totals"]["delta"] == 0
    assert payload["totals"]["reduction_pct"] == 0.0


def test_legacy_burndown_can_pick_baseline_from_history(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    current = tmp_path / "current.json"
    older = history / "older.json"
    newer = history / "newer.json"
    current.write_text(json.dumps({"count": 5, "findings": []}), encoding="utf-8")
    older.write_text(json.dumps({"count": 9, "findings": []}), encoding="utf-8")
    newer.write_text(json.dumps({"count": 8, "findings": []}), encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 10, now - 10))
    os.utime(newer, (now, now))

    proc = _run(
        "--current",
        str(current),
        "--baseline-from-history",
        str(history),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["baseline_source"].endswith("newer.json")
    assert payload["totals"]["baseline"] == 8
