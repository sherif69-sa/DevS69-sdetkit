from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/render_gate_decision_summary.py").resolve()


def test_render_gate_decision_summary_no_ship_json(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    fast = tmp_path / "fast.json"
    release.write_text(
        json.dumps({"ok": False, "failed_steps": ["gate_fast"], "profile": "release"}),
        encoding="utf-8",
    )
    fast.write_text(
        json.dumps({"ok": False, "failed_steps": ["ruff"], "profile": "fast"}), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(fast),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert payload["review_required"] is True
    assert payload["validation_errors"] == []
    assert payload["artifacts"]["release"]["failed_steps"] == ["gate_fast"]
    assert payload["artifacts"]["fast"]["failed_steps"] == ["ruff"]


def test_render_gate_decision_summary_ship_text_allow_missing_fast(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(tmp_path / "missing-fast.json"),
            "--allow-missing-fast",
            "--format",
            "text",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "- **Decision:** ✅ SHIP" in proc.stdout
    assert "## Reviewer checklist" in proc.stdout
    assert "- not provided" in proc.stdout


def test_render_gate_decision_summary_fails_with_missing_release(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(tmp_path / "missing-release.json"),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "missing-release.json" in payload["release"]


def test_render_gate_decision_summary_reports_non_boolean_ok(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps({"ok": "true", "failed_steps": [], "profile": "release"}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--allow-missing-fast",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert any("expected boolean `ok`" in row for row in payload["validation_errors"])
