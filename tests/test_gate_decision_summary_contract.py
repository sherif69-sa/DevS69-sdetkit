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
                        "evidence_status": "current_valid",
                    },
                    "fast": {
                        "present": True,
                        "ok": False,
                        "failed_steps": ["ruff"],
                        "profile": "fast",
                        "evidence_status": "current_valid",
                    },
                },
                "reviewer_checklist": [
                    "Open release artifact first; confirm ok/failed_steps/profile.",
                    "If release failed on gate_fast, open fast-gate artifact and fix first failing step.",
                    "Record one remediation action and expected rerun command in PR/release notes.",
                ],
                "next_action": {
                    "decision": "NO-SHIP",
                    "classification": "ruff",
                    "first_failure": "ruff",
                    "affected_file": "",
                    "next_command": (
                        "python -m sdetkit gate fast --format json --stable-json "
                        "--out build/gate-fast.json"
                    ),
                    "authority": "review-first",
                },
                "input_provenance": {
                    "digest_algorithm": "sha256",
                    "input_digest": "a" * 64,
                    "generated_from_head_sha": "b" * 40,
                    "input_digests": {"release": "c" * 64, "fast": "d" * 64},
                },
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
    assert any("decision must match two-artifact SHIP contract" in row for row in payload["errors"])


def test_gate_decision_summary_contract_rejects_ship_when_fast_failed(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "gate-decision-summary.json"
    release = tmp_path / "release-preflight.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.gate_decision_summary.v1",
                "decision": "SHIP",
                "headline": "Release preflight passed: candidate is ready to ship.",
                "review_required": False,
                "validation_errors": [],
                "artifacts": {
                    "release": {
                        "ok": True,
                        "failed_steps": [],
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
                    "Confirm both artifacts ok=true and failed_steps empty.",
                ],
            }
        ),
        encoding="utf-8",
    )
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}),
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
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any("decision must match two-artifact SHIP contract" in row for row in payload["errors"])


def test_gate_decision_summary_contract_requires_provenance_and_next_action(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "gate-decision-summary.json"
    release = tmp_path / "release-preflight.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.gate_decision_summary.v1",
                "decision": "SHIP",
                "headline": "Fast gate and release preflight passed: candidate is ready to ship.",
                "review_required": False,
                "validation_errors": [],
                "artifacts": {
                    "release": {
                        "ok": True,
                        "failed_steps": [],
                        "profile": "release",
                        "evidence_status": "current_valid",
                    },
                    "fast": {
                        "present": True,
                        "ok": True,
                        "failed_steps": [],
                        "profile": "fast",
                        "evidence_status": "current_valid",
                    },
                },
                "reviewer_checklist": [
                    "Confirm both artifacts ok=true and failed_steps empty.",
                ],
            }
        ),
        encoding="utf-8",
    )
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}),
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
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any("input_provenance" in row for row in payload["errors"])
    assert any("next_action" in row for row in payload["errors"])
