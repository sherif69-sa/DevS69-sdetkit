from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_ops_premerge_next_text_output(tmp_path: Path) -> None:
    gate = tmp_path / "premerge.json"
    gate.write_text(
        json.dumps(
            {
                "ok": True,
                "steps": [
                    {
                        "id": "enterprise_assessment",
                        "stdout": json.dumps(
                            {
                                "action_board": {
                                    "next": [
                                        {
                                            "priority": "P1",
                                            "check_id": "workflow_sprawl_risk",
                                            "action": "Consolidate overlapping workflows.",
                                        }
                                    ]
                                }
                            }
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/ops_premerge_next.py",
        "--gate-json",
        str(gate),
        "--limit",
        "2",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    out = result.stdout

    assert "OPS_PREMERGE_OK=True" in out
    assert "OPS_NEXT_COMMAND=make ops-weekly" in out
    assert "1. [P1] Consolidate overlapping workflows." in out


def test_ops_premerge_next_json_output_on_failure(tmp_path: Path) -> None:
    gate = tmp_path / "premerge.json"
    gate.write_text(json.dumps({"ok": False, "steps": []}), encoding="utf-8")

    cmd = [
        sys.executable,
        "scripts/ops_premerge_next.py",
        "--gate-json",
        str(gate),
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["ok"] is False
    assert payload["next_command"] == "make ops-premerge"


def test_ops_premerge_next_suggests_fast_lane_for_clean_tree_blocker(tmp_path: Path) -> None:
    gate = tmp_path / "premerge.json"
    gate.write_text(
        json.dumps(
            {
                "ok": False,
                "steps": [
                    {
                        "id": "ship_readiness",
                        "stdout": json.dumps(
                            {
                                "blockers": [
                                    {
                                        "check_id": "doctor_release.clean_tree",
                                        "status": "fail",
                                    }
                                ]
                            }
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/ops_premerge_next.py",
        "--gate-json",
        str(gate),
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["ok"] is False
    assert payload["next_command"] == "make ops-premerge-fast"


def test_ops_premerge_next_uses_doctor_release_report_for_gate_release_failure(
    tmp_path: Path,
) -> None:
    gate = tmp_path / "premerge.json"
    gate.write_text(
        json.dumps(
            {
                "ok": False,
                "steps": [
                    {
                        "id": "ship_readiness",
                        "stdout": json.dumps(
                            {
                                "runs": [
                                    {
                                        "id": "gate_release",
                                        "parsed_json": {
                                            "failed_steps": ["doctor_release"],
                                            "dry_run": False,
                                            "recommendations": [
                                                "Inspect release readiness output: python -m sdetkit doctor --release --format json --out build/doctor-release.json."
                                            ],
                                        },
                                    }
                                ]
                            }
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    doctor_report = tmp_path / "build/doctor-release.json"
    doctor_report.parent.mkdir(parents=True, exist_ok=True)
    doctor_report.write_text(
        json.dumps(
            {
                "checks": {
                    "clean_tree": {
                        "ok": False,
                        "summary": "working tree has uncommitted changes",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str((Path("scripts") / "ops_premerge_next.py").resolve()),
        "--gate-json",
        str(gate),
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(tmp_path))
    payload = json.loads(result.stdout)

    assert payload["ok"] is False
    assert payload["next_command"] == "make ops-premerge-fast"
