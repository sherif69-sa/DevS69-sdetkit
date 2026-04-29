from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_render_ops_bundle_trend_report(tmp_path: Path) -> None:
    trend = tmp_path / "trend.json"
    trend.write_text(
        json.dumps({"recent_runs": 3, "recent_passes": 2, "recent_pass_rate": 0.6667, "ok": False}),
        encoding="utf-8",
    )
    history = tmp_path / "history.jsonl"
    history.write_text(
        "\n".join([
            json.dumps({"ts": "2026-01-01T00:00:00+00:00", "ok": True, "missing_count": 0}),
            json.dumps({"ts": "2026-01-02T00:00:00+00:00", "ok": False, "missing_count": 1}),
        ])
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "trend.md"
    subprocess.run([
        sys.executable,
        "scripts/render_ops_bundle_trend_report.py",
        "--trend", str(trend),
        "--history", str(history),
        "--out-md", str(out),
        "--format", "json",
    ], check=True)

    content = out.read_text(encoding="utf-8")
    assert "recent pass rate" in content
    assert "2026-01-02" in content
