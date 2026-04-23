from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_render_impact_pr_comment_creates_markdown(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    _write_json(build / "impact-release-guard.json", {"ok": True, "reason": "release_ready"})
    _write_json(
        build / "impact-adaptive-review.json",
        {"overall_score": 93, "weakest_head": "velocity_head", "status": "strong"},
    )
    _write_json(build / "impact-next-plan.json", {"now": ["Action one"], "next": [], "later": []})
    _write_json(build / "impact-step1-scorecard.json", {"achieved_pct": 96.5, "status": "strong"})
    _write_json(build / "impact-program-scorecard.json", {"overall_score": 91.2, "status": "strong"})
    _write_json(
        build / "impact-step-scorecards.json",
        {"scorecards": {"step_2": {"achieved_pct": 94.0, "status": "strong"}, "step_3": {"achieved_pct": 92.0, "status": "strong"}}},
    )

    db = build / "impact-intelligence.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE impact_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, overall_score REAL)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (70)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (80)")
        conn.execute("INSERT INTO impact_runs (overall_score) VALUES (93)")

    out = build / "impact-pr-comment.md"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/render_impact_pr_comment.py",
            "--build-dir",
            str(build),
            "--out",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    body = out.read_text(encoding="utf-8")
    assert "Impact Release Control Summary" in body
    assert "PASS" in body
    assert "Action one" in body
    assert "🟢" in body
    assert "+13.00" in body
    assert "improving" in body
    assert "Trend gate: `pass`" in body
    assert "docs/recommended-ci-flow.md" in body
    assert "96.5%" in body
    assert "91.2" in body
    assert "94.0%" in body
    assert "92.0%" in body
