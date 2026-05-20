from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sdetkit.check_intelligence import build_check_intelligence
from sdetkit.diagnostic_vector_engine import build_diagnostic_vector
from sdetkit.pr_quality_remediation_refresh import (
    ASSESS_GREEN_AFTER_SAFE_FIX,
    build_remediation_refresh,
)
from sdetkit.remediation_plan_engine import build_remediation_plan
from sdetkit.safe_fix_history_memory import build_safe_fix_history


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in (
        "diagnoses",
        "diagnostic_vectors",
        "vectors",
        "plans",
        "remediation_plans",
        "items",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            if rows:
                return rows

    if any(
        key in payload
        for key in (
            "failure_surface",
            "safe_to_auto_fix",
            "allowed_strategy",
            "recommended_next_action",
        )
    ):
        return [payload]

    rows: list[dict[str, Any]] = []
    for value in payload.values():
        rows.extend(_records(value))
    return rows


def _find_safe_format_plan(payload: dict[str, Any]) -> dict[str, Any]:
    for row in _records(payload):
        if row.get("safe_to_auto_fix") is True and row.get("allowed_strategy") == "run_pre_commit":
            return row
    raise AssertionError(f"no safe run_pre_commit plan found in {payload}")


def test_end_to_end_formatting_remediation_scenario_harness(tmp_path: Path) -> None:
    target_file = "src/sdetkit/operator_brief.py"

    checks_json = _write_json(
        tmp_path / "checks.json",
        {
            "check_runs": [
                {
                    "name": "autopilot",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Run maintenance autopilot",
                            "ruff format..............................................................Failed",
                            "- hook id: ruff-format",
                            "- files were modified by this hook",
                            f"would reformat {target_file}",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = build_check_intelligence(checks_json=checks_json)
    failed_check = intelligence["failed_checks"][0]
    first_failure = failed_check["first_failure"]

    assert failed_check["name"] == "autopilot"
    first_failure_line = str(first_failure["line"])
    assert (
        "ruff format" in first_failure_line
        or "ruff-format" in first_failure_line
        or "files were modified" in first_failure_line
    )
    assert "Using cached" not in first_failure_line

    safe_remediation = {
        "safe_to_auto_fix": True,
        "strategy": "run_pre_commit",
        "affected_files": [target_file],
        "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
    }

    _, initial_trends, _ = build_safe_fix_history(
        {
            "safe_fix_outcomes": [
                {
                    "timestamp": "2026-05-20T00:00:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": [target_file],
                    "safe_to_auto_fix": True,
                    "pushed": True,
                    "committed": True,
                }
            ]
        },
        observed_at="2026-05-20T00:10:00Z",
    )

    diagnostic_vector = build_diagnostic_vector(
        check_intelligence=intelligence,
        safe_remediation=safe_remediation,
        safe_fix_history=initial_trends,
        generated_at="2026-05-20T00:20:00Z",
    )
    diagnostic_records = _records(diagnostic_vector)

    assert any(
        row.get("safe_fix_candidate") is True
        or row.get("safe_to_auto_fix") is True
        or row.get("recommended_next_action") == "run_pre_commit"
        for row in diagnostic_records
    )

    remediation_plan = build_remediation_plan(
        diagnostic_vector,
        generated_at="2026-05-20T00:30:00Z",
    )
    safe_plan = _find_safe_format_plan(remediation_plan)

    assert safe_plan["safe_to_auto_fix"] is True
    assert safe_plan["allowed_strategy"] == "run_pre_commit"
    assert target_file in safe_plan.get("affected_files", [])

    plan_path = _write_json(tmp_path / "remediation-plan.json", remediation_plan)
    autopilot_out = tmp_path / "autopilot"

    bridge = subprocess.run(
        [
            sys.executable,
            "tools/maintenance_autopilot.py",
            "--owner",
            "sherif69-sa",
            "--repo",
            "DevS69-sdetkit",
            "--remediation-plan-json",
            str(plan_path),
            "--pr-quality-safe-bridge-only",
            "--out-dir",
            str(autopilot_out),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert bridge.returncode == 0, bridge.stdout + bridge.stderr

    bridge_json = sorted(autopilot_out.rglob("*.json"))
    assert bridge_json, bridge.stdout + bridge.stderr
    bridge_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in bridge_json
    ]
    bridge_text = "\n".join(
        json.dumps(payload, sort_keys=True)
        for payload in bridge_payloads
    )
    assert str(plan_path) in bridge_text
    assert "safe bridge only" in bridge_text
    assert "review_first_security_review" not in bridge_text
    assert any(
        payload.get("live_run", {}).get("attempted") is False
        for payload in bridge_payloads
        if isinstance(payload, dict)
    )

    safe_fix_outcome = {
        "attempted": True,
        "committed": True,
        "pushed": True,
        "commit_sha": "new-head-sha",
        "previous_head_sha": "old-head-sha",
        "files": [target_file],
        "status": "pushed",
        "remediation_ok": True,
    }

    refresh = build_remediation_refresh(
        check_intelligence={
            "current_pr_head_sha": "new-head-sha",
            "failed_checks": [],
            "queued_checks": [],
        },
        safe_fix_outcome=safe_fix_outcome,
    )

    assert refresh["safe_fix_pushed"] is True
    assert refresh["refreshed_head_sha"] == "new-head-sha"
    assert refresh["proof_after_fix_passed"] is True
    assert refresh["merge_assessment"] == ASSESS_GREEN_AFTER_SAFE_FIX

    _, final_trends, history_markdown = build_safe_fix_history(
        {
            "safe_fix_outcomes": [
                {
                    "timestamp": "2026-05-20T00:00:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": [target_file],
                    "safe_to_auto_fix": True,
                    "pushed": True,
                    "committed": True,
                },
                {
                    "timestamp": "2026-05-20T00:40:00Z",
                    "status": "pushed",
                    "classification": "format_only",
                    "affected_files": [target_file],
                    "safe_to_auto_fix": True,
                    "pushed": True,
                    "committed": True,
                },
            ]
        },
        observed_at="2026-05-20T00:50:00Z",
    )

    metrics = final_trends["metrics"]
    assert metrics["format_drift_owner_files"] == [
        {
            "file": target_file,
            "count": 2,
            "owner_signal": "recurring_format_drift",
        }
    ]
    assert metrics["owner_file_guardrail_recommendations"]
    assert metrics["local_dev_guardrail_recommendations"]
    assert "Owner-file guardrail recommendations" in history_markdown
