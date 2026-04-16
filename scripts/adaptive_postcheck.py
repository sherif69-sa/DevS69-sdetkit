#!/usr/bin/env python3
"""Run adaptive reviewer/engine/agent alignment post-checks.

Supports scenario-driven checks so post-check behavior can evolve without code
changes, making automation adaptive rather than fixed-date/fixed-rule.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = ROOT / "docs/contracts/adaptive-postcheck-scenarios.v1.json"


def _load_review_payload(repo_root: str, input_json: str | None) -> dict[str, Any]:
    if input_json:
        return json.loads(Path(input_json).read_text(encoding="utf-8"))

    cmd = [
        sys.executable,
        "-m",
        "sdetkit",
        "review",
        repo_root,
        "--no-workspace",
        "--format",
        "json",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    raise RuntimeError(
        "failed to load review payload from command; "
        f"exit={result.returncode}, stderr={result.stderr.strip()!r}"
    )


def _load_scenario(name: str) -> dict[str, Any]:
    payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", {})
    if not isinstance(scenarios, dict) or name not in scenarios:
        available = ", ".join(sorted(scenarios)) if isinstance(scenarios, dict) else ""
        raise ValueError(f"unknown scenario {name!r}; available: {available}")
    selected = scenarios[name]
    if not isinstance(selected, dict):
        raise ValueError(f"scenario {name!r} is invalid")
    return selected




def _latest_artifact(prefix: str) -> Path | None:
    candidates = sorted((ROOT / "docs/artifacts").glob(f"{prefix}*.json"))
    return candidates[-1] if candidates else None


def _load_latest_scenario_database() -> dict[str, Any] | None:
    latest = _latest_artifact("adaptive-scenario-database-")
    if latest is None:
        return None
    payload = json.loads(latest.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _doctor_summary(repo_root: str) -> dict[str, Any] | None:
    cmd = [sys.executable, "-m", "sdetkit", "doctor", "--format", "json"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=repo_root)
    if not result.stdout.strip():
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "ok": bool(payload.get("ok", False)),
        "score": payload.get("score"),
        "failed_checks": payload.get("quality", {}).get("failed_checks"),
        "failed_check_ids": payload.get("quality", {}).get("failed_check_ids", []),
    }


def _bool_check(name: str, passed: bool, details: str, severity: str = "required") -> dict[str, Any]:
    return {"check": name, "passed": passed, "details": details, "severity": severity}


def _run_alignment_checks(payload: dict[str, Any], scenario: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    enabled = set(scenario.get("enabled_checks", []))
    warn_checks = set(scenario.get("warn_only_checks", []))

    def severity_for(check_name: str) -> str:
        return "warn" if check_name in warn_checks else "required"

    adaptive = payload.get("adaptive_database")
    if "adaptive_database_present" in enabled:
        checks.append(
            _bool_check(
                "adaptive_database_present",
                isinstance(adaptive, dict),
                "adaptive_database must be present in review payload",
                severity_for("adaptive_database_present"),
            )
        )
    if not isinstance(adaptive, dict):
        return checks

    contract = adaptive.get("release_readiness_contract")
    if "release_readiness_contract_present" in enabled:
        checks.append(
            _bool_check(
                "release_readiness_contract_present",
                isinstance(contract, dict),
                "release_readiness_contract should exist under adaptive_database",
                severity_for("release_readiness_contract_present"),
            )
        )
    if not isinstance(contract, dict):
        return checks

    backlog = contract.get("recommendation_backlog")
    agent_orchestration = contract.get("agent_orchestration")
    if not isinstance(backlog, list):
        backlog = []
    if not isinstance(agent_orchestration, list):
        agent_orchestration = []

    if "agent_orchestration_present_when_backlog_exists" in enabled:
        checks.append(
            _bool_check(
                "agent_orchestration_present_when_backlog_exists",
                (not backlog) or bool(agent_orchestration),
                "if recommendation backlog exists, agent orchestration should be non-empty",
                severity_for("agent_orchestration_present_when_backlog_exists"),
            )
        )

    if "agent_entries_include_engine_signals" in enabled:
        has_engine_signals = all(
            isinstance(row, dict) and isinstance(row.get("engine_signals"), list)
            for row in agent_orchestration
        )
        checks.append(
            _bool_check(
                "agent_entries_include_engine_signals",
                has_engine_signals,
                "each agent_orchestration row should include engine_signals list",
                severity_for("agent_entries_include_engine_signals"),
            )
        )

    if "recommendation_backlog_sorted_desc" in enabled:
        priority_values: list[float] = []
        for row in backlog:
            if isinstance(row, dict) and isinstance(row.get("priority_index"), (int, float)):
                priority_values.append(float(row["priority_index"]))

        is_sorted = priority_values == sorted(priority_values, reverse=True)
        checks.append(
            _bool_check(
                "recommendation_backlog_sorted_desc",
                is_sorted,
                "recommendation backlog should be sorted by priority_index descending",
                severity_for("recommendation_backlog_sorted_desc"),
            )
        )

    scenario_db = _load_latest_scenario_database()
    if "scenario_database_minimum_coverage" in enabled:
        total = int((scenario_db or {}).get("summary", {}).get("total_scenarios", 0))
        minimum = int(scenario.get("scenario_minimum", 500))
        checks.append(
            _bool_check(
                "scenario_database_minimum_coverage",
                total >= minimum,
                f"scenario database should have at least {minimum} active scenarios (found {total})",
                severity_for("scenario_database_minimum_coverage"),
            )
        )

    return checks


def _default_out_path() -> str:
    date_tag = datetime.now(timezone.utc).date().isoformat()
    return f"docs/artifacts/adaptive-postcheck-{date_tag}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--input-json", default=None, help="Path to existing review JSON payload")
    ap.add_argument("--scenario", default="balanced", help="Scenario name from adaptive-postcheck-scenarios contract")
    ap.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: docs/artifacts/adaptive-postcheck-YYYY-MM-DD.json)",
    )
    args = ap.parse_args()

    payload = _load_review_payload(args.repo, args.input_json)
    scenario = _load_scenario(args.scenario)
    checks = _run_alignment_checks(payload, scenario)
    doctor = _doctor_summary(args.repo)
    passed = sum(1 for c in checks if c.get("passed"))
    failed_required = sum(1 for c in checks if (not c.get("passed")) and c.get("severity") != "warn")
    failed_warn = sum(1 for c in checks if (not c.get("passed")) and c.get("severity") == "warn")

    out_payload = {
        "schema_version": "sdetkit.adaptive-postcheck.v1",
        "scenario": args.scenario,
        "generated_from": args.input_json or "runtime review command",
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed_required": failed_required,
            "failed_warn": failed_warn,
            "ok": failed_required == 0,
        },
        "checks": checks,
        "doctor": doctor,
    }

    out_path = Path(args.out or _default_out_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(out_payload["summary"], sort_keys=True))
    return 0 if out_payload["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
