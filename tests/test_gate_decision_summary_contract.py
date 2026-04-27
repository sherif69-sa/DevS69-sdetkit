from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_gate_decision_summary_contract.py").resolve()


def test_gate_decision_summary_contract_ok(tmp_path: Path) -> None:
    summary = tmp_path / "gate-decision-summary.json"
    release = tmp_path / "release-preflight.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.gate_decision_summary.v1",
                "decision": "NO-SHIP",
                "headline": "Release preflight failed: do not ship until blockers are resolved.",
                "review_required": True,
                "validation_errors": [],
                "artifacts": {
                    "release": {
                        "ok": False,
                        "failed_steps": ["gate_fast"],
                        "profile": "release",
                    },
                    "fast": {
                        "present": True,
                        "ok": False,
                        "failed_steps": ["ruff"],
                        "profile": "fast",
                    },
                },
                "reviewer_checklist": [
                    "Open release artifact first; confirm ok/failed_steps/profile.",
                    "If release failed on gate_fast, open fast-gate artifact and fix first failing step.",
                    "Record one remediation action and expected rerun command in PR/release notes.",
                ],
            }
        ),
        encoding="utf-8",
    )
    release.write_text(
        json.dumps({"ok": False, "failed_steps": ["gate_fast"], "profile": "release"}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(summary),
            "--release",
            str(release),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_gate_decision_summary_contract_detects_mismatch(tmp_path: Path) -> None:
    summary = tmp_path / "gate-decision-summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.gate_decision_summary.v1",
                "decision": "SHIP",
                "headline": "incorrect",
                "review_required": False,
                "validation_errors": [],
                "artifacts": {
                    "release": {"ok": False, "failed_steps": ["gate_fast"], "profile": "release"},
                    "fast": {"present": False, "ok": None, "failed_steps": [], "profile": None},
                },
                "reviewer_checklist": ["one"],
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--summary",
            str(summary),
            "--allow-missing-release",
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
    assert any("decision must match artifacts.release.ok" in row for row in payload["errors"])
