#!/usr/bin/env python3
"""Run adaptive reviewer/engine/agent alignment post-checks.

Supports scenario-driven checks so post-check behavior can evolve without code
changes, making automation adaptive rather than fixed-date/fixed-rule.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess as _subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = ROOT / "docs/contracts/adaptive-postcheck-scenarios.v1.json"
SCENARIO_DB_SCRIPT = ROOT / "scripts/build_adaptive_scenario_database.py"


class _SubprocessFacade:
    """Local subprocess facade so tests can monkeypatch run() without global side effects."""

    run = staticmethod(_subprocess.run)


subprocess = _SubprocessFacade()


def _local_python_env(repo_root: str) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "").strip()
    candidate_root = Path(repo_root).resolve()
    src_path = str((candidate_root / "src").resolve())
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _parse_json_stdout(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = None
    if isinstance(loaded, dict):
        return loaded

    for line in reversed(raw.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        if not (candidate.startswith("{") and candidate.endswith("}")):
            continue
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


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
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=_local_python_env(repo_root),
    )
    parsed = _parse_json_stdout(result.stdout)
    if isinstance(parsed, dict):
        return parsed
    raise RuntimeError(
        "failed to load review payload from command; "
        f"exit={result.returncode}, stdout={result.stdout.strip()[:200]!r}, stderr={result.stderr.strip()!r}"
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


def _build_fresh_scenario_database(
    out_path: Path | None = None, *, persist: bool = False
) -> dict[str, Any] | None:
    should_cleanup_out = False
    if out_path is None:
        if persist:
            date_tag = datetime.now(UTC).date().isoformat()
            out_path = ROOT / "docs/artifacts" / f"adaptive-scenario-database-{date_tag}.json"
        else:
            fd, path = tempfile.mkstemp(prefix="adaptive-scenario-database-", suffix=".json")
            os.close(fd)
            out_path = Path(path)
            should_cleanup_out = True
    elif not persist:
        should_cleanup_out = True
    cmd = [sys.executable, str(SCENARIO_DB_SCRIPT), ".", "--out", str(out_path)]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=_local_python_env(str(ROOT)),
    )
    if result.returncode != 0:
        if should_cleanup_out and out_path.exists():
            out_path.unlink()
        return None
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    if should_cleanup_out and out_path.exists():
        out_path.unlink()
    return payload if isinstance(payload, dict) else None


def _resolve_scenario_database(
    *,
    minimum: int,
    minimum_matrix_rows: int,
    refresh_when_stale: bool,
    persist_refresh_artifact: bool,
) -> tuple[dict[str, Any] | None, str]:
    scenario_db = _load_latest_scenario_database()
    source = "latest-artifact"
    summary = (scenario_db or {}).get("summary", {})
    total = int(summary.get("total_scenarios", 0)) if isinstance(summary, dict) else 0
    kinds = summary.get("kinds", {}) if isinstance(summary, dict) else {}
    matrix_count = int(kinds.get("adaptive_reviewer_matrix", 0)) if isinstance(kinds, dict) else 0

    is_stale = total < minimum or matrix_count < minimum_matrix_rows
    if refresh_when_stale and is_stale:
        refreshed = _build_fresh_scenario_database(persist=persist_refresh_artifact)
        if isinstance(refreshed, dict):
            scenario_db = refreshed
            source = "refreshed-runtime"
    return scenario_db, source


def _load_workflow_consolidation_plan() -> dict[str, Any] | None:
    plan_path = ROOT / "docs/contracts/workflow-consolidation-plan.v1.json"
    if not plan_path.is_file():
        return None
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _doctor_summary(repo_root: str) -> dict[str, Any] | None:
    cmd = [sys.executable, "-m", "sdetkit", "doctor", "--format", "json"]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=_local_python_env(repo_root),
    )
    payload = _parse_json_stdout(result.stdout)
    if not isinstance(payload, dict):
        return None
    return {
        "ok": bool(payload.get("ok", False)),
        "score": payload.get("score"),
        "failed_checks": payload.get("quality", {}).get("failed_checks"),
        "failed_check_ids": payload.get("quality", {}).get("failed_check_ids", []),
    }


def _bool_check(
    name: str, passed: bool, details: str, severity: str = "required"
) -> dict[str, Any]:
    return {"check": name, "passed": passed, "details": details, "severity": severity}


def _run_alignment_checks(
    payload: dict[str, Any],
    scenario: dict[str, Any],
    first_run_triage: dict[str, Any],
    scenario_db: dict[str, Any] | None,
    plan_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
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

        def _has_signals(row: Any) -> bool:
            if not isinstance(row, dict):
                return False
            for key in ("engine_signals", "signals", "evidence_signals"):
                if isinstance(row.get(key), (list, dict)):
                    return True
            return False

        has_engine_signals = all(_has_signals(row) for row in agent_orchestration)
        checks.append(
            _bool_check(
                "agent_entries_include_engine_signals",
                has_engine_signals,
                "each agent_orchestration row should include a signals list (engine_signals/signals/evidence_signals)",
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

    if "six_phase_workflow_ready" in enabled:
        phases = []
        if isinstance(plan_payload, dict):
            raw_phases = plan_payload.get("phases", [])
            if isinstance(raw_phases, list):
                phases = [str(x) for x in raw_phases]
        checks.append(
            _bool_check(
                "six_phase_workflow_ready",
                len(phases) == 6,
                f"workflow consolidation plan should define exactly 6 phases (found {len(phases)})",
                severity_for("six_phase_workflow_ready"),
            )
        )

    if "intelligence_matrix_present" in enabled:
        kinds = (scenario_db or {}).get("summary", {}).get("kinds", {})
        matrix_count = 0
        if isinstance(kinds, dict):
            matrix_count = int(kinds.get("adaptive_reviewer_matrix", 0))
        checks.append(
            _bool_check(
                "intelligence_matrix_present",
                matrix_count >= 1000,
                (
                    "adaptive reviewer intelligence matrix should provide broad coverage "
                    f"(adaptive_reviewer_matrix={matrix_count})"
                ),
                severity_for("intelligence_matrix_present"),
            )
        )

    if "first_run_hints_present" in enabled:
        hint_count = int(first_run_triage.get("hint_count", 0))
        checks.append(
            _bool_check(
                "first_run_hints_present",
                hint_count > 0,
                f"first-run triage should provide actionable hints when issues exist (hints={hint_count})",
                severity_for("first_run_hints_present"),
            )
        )

    return checks


def _build_follow_up_enhancements(
    *,
    checks: list[dict[str, Any]],
    scenario_db: dict[str, Any] | None,
    plan_payload: dict[str, Any] | None,
) -> list[dict[str, str]]:
    by_name = {str(row.get("check", "")): row for row in checks if isinstance(row, dict)}
    summary = (scenario_db or {}).get("summary", {})
    total = int(summary.get("total_scenarios", 0)) if isinstance(summary, dict) else 0
    phases = plan_payload.get("phases", []) if isinstance(plan_payload, dict) else []
    phase_count = len(phases) if isinstance(phases, list) else 0

    enhancements: list[dict[str, str]] = []
    if not bool(by_name.get("six_phase_workflow_ready", {}).get("passed", False)):
        enhancements.append(
            {
                "id": "workflow-phase-sequencing",
                "area": "workflow",
                "priority": "high",
                "feature": "Add phase handoff gates with explicit entry/exit contracts for all 6 phases.",
                "next_command": "python scripts/phase_sequential_executor.py --help",
            }
        )
    if not bool(by_name.get("intelligence_matrix_present", {}).get("passed", False)):
        enhancements.append(
            {
                "id": "intelligence-matrix-growth",
                "area": "intelligence",
                "priority": "high",
                "feature": "Expand adaptive reviewer matrix combinations and add confidence-calibration scoring.",
                "next_command": "python scripts/build_adaptive_scenario_database.py --out docs/artifacts/adaptive-scenario-database-$(date +%F).json",
            }
        )
    if total < 5000:
        enhancements.append(
            {
                "id": "scenario-database-expansion",
                "area": "database",
                "priority": "medium",
                "feature": "Grow scenario database to 5000+ entries with weekly refresh automation.",
                "next_command": "make adaptive-scenario-db",
            }
        )
    if phase_count == 6:
        enhancements.append(
            {
                "id": "phase6-outcome-intel",
                "area": "reviewer",
                "priority": "medium",
                "feature": "Publish per-phase adaptive reviewer outcome summaries for operator dashboards.",
                "next_command": "make adaptive-ops-bundle",
            }
        )
    return enhancements


def _render_markdown_summary(
    *,
    scenario: str,
    summary: dict[str, Any],
    checks: list[dict[str, Any]],
    follow_up_enhancements: list[dict[str, str]],
    scenario_database: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Adaptive Postcheck Summary")
    lines.append("")
    lines.append(f"- Scenario: `{scenario}`")
    lines.append(f"- OK: `{bool(summary.get('ok', False))}`")
    lines.append(f"- Passed: `{int(summary.get('passed', 0))}/{int(summary.get('total', 0))}`")
    lines.append(f"- Confidence score: `{int(summary.get('confidence_score', 0))}`")
    if isinstance(summary.get("confidence_band"), str):
        lines.append(f"- Confidence band: `{summary.get('confidence_band')}`")
    if isinstance(summary.get("confidence_trend"), str):
        lines.append(f"- Confidence trend: `{summary.get('confidence_trend')}`")
    lines.append(
        "- Scenario DB: "
        f"`{scenario_database.get('source', 'unknown')}` "
        f"({int(scenario_database.get('total_scenarios', 0))} scenarios)"
    )
    lines.append("")
    if isinstance(scenario_database.get("domain_confidence"), dict):
        lines.append("## Domain Confidence")
        for domain, score in sorted(scenario_database.get("domain_confidence", {}).items()):
            lines.append(f"- `{domain}`: `{int(score)}`")
        lines.append("")

    lines.append("")
    lines.append("## Check Results")
    for row in checks:
        if not isinstance(row, dict):
            continue
        icon = "✅" if bool(row.get("passed", False)) else "❌"
        lines.append(
            f"- {icon} `{row.get('check', 'unknown')}` ({row.get('severity', 'required')}): {row.get('details', '')}"
        )
    lines.append("")
    lines.append("## Follow-up Enhancements")
    if not follow_up_enhancements:
        lines.append("- No additional enhancements recommended.")
    else:
        for row in follow_up_enhancements:
            lines.append(
                f"- **{row.get('id', 'unknown')}** [{row.get('priority', 'medium')}/{row.get('area', 'general')}]: "
                f"{row.get('feature', '')}"
            )
            next_cmd = row.get("next_command", "")
            if next_cmd:
                lines.append(f"  - Next command: `{next_cmd}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def _compute_confidence_score(
    *, checks: list[dict[str, Any]], scenario_db: dict[str, Any] | None, scenario_minimum: int
) -> int:
    total = max(1, len(checks))
    passed = sum(1 for row in checks if bool(row.get("passed", False)))
    pass_rate = passed / total

    summary = (scenario_db or {}).get("summary", {})
    total_scenarios = int(summary.get("total_scenarios", 0)) if isinstance(summary, dict) else 0
    kinds = summary.get("kinds", {}) if isinstance(summary, dict) else {}
    matrix_count = int(kinds.get("adaptive_reviewer_matrix", 0)) if isinstance(kinds, dict) else 0

    db_ratio = min(1.0, total_scenarios / max(1, scenario_minimum))
    matrix_ratio = min(1.0, matrix_count / 1000.0)

    # Weighted blend, deterministic integer score [0, 100].
    score = (pass_rate * 70.0) + (db_ratio * 20.0) + (matrix_ratio * 10.0)
    return max(0, min(100, int(round(score))))


def _confidence_band(score: int) -> dict[str, str]:
    if score >= 90:
        return {
            "band": "auto-approve-candidate",
            "routing": "light-review",
            "operator_action": "Proceed with a lightweight reviewer pass and ship-readiness confirmation.",
        }
    if score >= 70:
        return {
            "band": "manual-review",
            "routing": "manual-reviewer-required",
            "operator_action": "Route to reviewer with targeted follow-up enhancements before release decision.",
        }
    return {
        "band": "remediation-required",
        "routing": "block-and-remediate",
        "operator_action": "Block release progression and execute remediation actions first.",
    }


def _update_confidence_history(
    *, history_path: Path, score: int, max_entries: int = 20
) -> dict[str, Any]:
    if history_path.exists():
        loaded = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        loaded = {"entries": []}
    entries = loaded.get("entries", []) if isinstance(loaded, dict) else []
    if not isinstance(entries, list):
        entries = []

    entries.append(
        {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "score": int(score),
        }
    )
    entries = entries[-max_entries:]

    trend = "insufficient-history"
    trend_window = [int(row.get("score", 0)) for row in entries[-7:] if isinstance(row, dict)]
    if len(trend_window) >= 4:
        split = len(trend_window) // 2
        first_avg = sum(trend_window[:split]) / max(1, split)
        second_avg = sum(trend_window[split:]) / max(1, len(trend_window) - split)
        delta = second_avg - first_avg
        if delta >= 3.0:
            trend = "improving"
        elif delta <= -3.0:
            trend = "regressing"
        else:
            trend = "stable"

    payload = {
        "schema_version": "sdetkit.adaptive-postcheck-history.v1",
        "entries": entries,
        "trend": trend,
        "trend_window_size": len(trend_window),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def _next_follow_up_plan(confidence_band: str, confidence_trend: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = [
        {
            "id": "weekly-adaptive-ops",
            "priority": "medium",
            "task": "Run adaptive ops bundle weekly and review confidence trajectory.",
            "command": "make adaptive-ops-bundle",
        }
    ]
    if confidence_band != "auto-approve-candidate":
        steps.insert(
            0,
            {
                "id": "targeted-remediation",
                "priority": "high",
                "task": "Execute top follow-up enhancements before release routing decision.",
                "command": "python scripts/adaptive_postcheck.py . --scenario strict --out build/adaptive-postcheck-strict.json",
            },
        )
    if confidence_trend == "regressing":
        steps.insert(
            0,
            {
                "id": "trend-regression-audit",
                "priority": "high",
                "task": "Audit last 3 postcheck runs and open a regression issue with evidence.",
                "command": "python scripts/build_adaptive_ops_summary.py",
            },
        )
    return steps


def _build_domain_confidence_snapshot(
    *, scenario_db: dict[str, Any] | None, scenario_minimum: int
) -> dict[str, int]:
    summary = (scenario_db or {}).get("summary", {})
    domains = summary.get("domains", {}) if isinstance(summary, dict) else {}
    if not isinstance(domains, dict):
        return {}
    domain_target = max(1.0, float(scenario_minimum) / 5.0)
    snapshot: dict[str, int] = {}
    for domain, count in domains.items():
        if not isinstance(domain, str):
            continue
        numeric = float(count) if isinstance(count, (int, float)) else 0.0
        score = int(round(max(0.0, min(100.0, (numeric / domain_target) * 100.0))))
        snapshot[domain] = score
    return dict(sorted(snapshot.items()))


def _build_first_run_triage(
    payload: dict[str, Any], doctor: dict[str, Any] | None
) -> dict[str, Any]:
    adaptive = (
        payload.get("adaptive_database", {})
        if isinstance(payload.get("adaptive_database"), dict)
        else {}
    )
    contract = (
        adaptive.get("release_readiness_contract", {})
        if isinstance(adaptive.get("release_readiness_contract"), dict)
        else {}
    )

    doctor_failed = []
    if isinstance(doctor, dict):
        raw_failed = doctor.get("failed_check_ids", [])
        if isinstance(raw_failed, list):
            doctor_failed = [str(x) for x in raw_failed]

    top_actions: list[str] = []
    raw_top_actions = payload.get("top_actions", [])
    if isinstance(raw_top_actions, list):
        top_actions.extend(str(x) for x in raw_top_actions[:5])

    recommendation_engine = contract.get("recommendation_engine", {})
    if isinstance(recommendation_engine, dict):
        for lane in ("now", "next", "watchlist"):
            rows = recommendation_engine.get(lane, [])
            if isinstance(rows, list):
                for row in rows[:3]:
                    if isinstance(row, dict):
                        action = row.get("action") or row.get("title") or row.get("summary")
                        if action:
                            top_actions.append(str(action))

    dedup_actions: list[str] = []
    seen: set[str] = set()
    for item in top_actions:
        if item not in seen:
            seen.add(item)
            dedup_actions.append(item)

    fix_hints: list[dict[str, str]] = []
    doctor_fix_map = {
        "pyproject": "Ensure pyproject.toml is valid and includes project metadata required by doctor.",
        "venv": "Create/activate .venv and install project deps before running gates.",
        "dev_tools": "Install required dev tools (ruff/mypy/pytest) via bootstrap/install lanes.",
    }
    for key in doctor_failed:
        hint = doctor_fix_map.get(key, f"Investigate failing doctor check: {key}")
        fix_hints.append({"source": "doctor", "issue": key, "hint": hint})

    for action in dedup_actions[:8]:
        fix_hints.append({"source": "review", "issue": "adaptive_action", "hint": action})

    status = "good" if not fix_hints else "needs-action"
    return {
        "status": status,
        "doctor_failed_checks": doctor_failed,
        "priority_hints": fix_hints,
        "hint_count": len(fix_hints),
    }


def _default_out_path() -> str:
    date_tag = datetime.now(UTC).date().isoformat()
    return f"docs/artifacts/adaptive-postcheck-{date_tag}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--input-json", default=None, help="Path to existing review JSON payload")
    ap.add_argument(
        "--scenario",
        default="balanced",
        help="Scenario name from adaptive-postcheck-scenarios contract",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: docs/artifacts/adaptive-postcheck-YYYY-MM-DD.json)",
    )
    ap.add_argument(
        "--out-md",
        default=None,
        help="Optional markdown summary output path (default: docs/artifacts/adaptive-postcheck-YYYY-MM-DD.md).",
    )
    ap.add_argument(
        "--no-refresh-scenario-db",
        action="store_true",
        help="Disable runtime refresh when latest scenario DB is below scenario threshold.",
    )
    ap.add_argument(
        "--persist-refreshed-scenario-db",
        action="store_true",
        help="Persist refreshed scenario DB artifact under docs/artifacts instead of using a temporary file.",
    )
    ap.add_argument(
        "--history-json",
        default=None,
        help="Optional confidence history JSON file; when provided, appends current score and emits trend.",
    )
    args = ap.parse_args()

    payload = _load_review_payload(args.repo, args.input_json)
    scenario = _load_scenario(args.scenario)
    minimum = int(scenario.get("scenario_minimum", 500))
    scenario_db, scenario_db_source = _resolve_scenario_database(
        minimum=minimum,
        minimum_matrix_rows=1000,
        refresh_when_stale=not args.no_refresh_scenario_db,
        persist_refresh_artifact=args.persist_refreshed_scenario_db,
    )
    plan_payload = _load_workflow_consolidation_plan()
    doctor = _doctor_summary(args.repo)
    first_run_triage = _build_first_run_triage(payload, doctor)
    checks = _run_alignment_checks(payload, scenario, first_run_triage, scenario_db, plan_payload)
    follow_up_enhancements = _build_follow_up_enhancements(
        checks=checks,
        scenario_db=scenario_db,
        plan_payload=plan_payload,
    )
    confidence_score = _compute_confidence_score(
        checks=checks,
        scenario_db=scenario_db,
        scenario_minimum=minimum,
    )
    confidence_guidance = _confidence_band(confidence_score)
    confidence_trend = "insufficient-history"
    if args.history_json:
        history = _update_confidence_history(
            history_path=Path(args.history_json), score=confidence_score
        )
        confidence_trend = str(history.get("trend", "insufficient-history"))
    next_plan = _next_follow_up_plan(
        confidence_band=confidence_guidance["band"],
        confidence_trend=confidence_trend,
    )
    domain_confidence = _build_domain_confidence_snapshot(
        scenario_db=scenario_db,
        scenario_minimum=minimum,
    )
    passed = sum(1 for c in checks if c.get("passed"))
    failed_required = sum(
        1 for c in checks if (not c.get("passed")) and c.get("severity") != "warn"
    )
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
            "confidence_score": confidence_score,
            "confidence_band": confidence_guidance["band"],
            "confidence_trend": confidence_trend,
        },
        "checks": checks,
        "doctor": doctor,
        "first_run_triage": first_run_triage,
        "scenario_database": {
            "source": scenario_db_source,
            "total_scenarios": int(
                (
                    (scenario_db or {}).get("summary", {}) if isinstance(scenario_db, dict) else {}
                ).get("total_scenarios", 0)
            ),
            "domain_confidence": domain_confidence,
        },
        "follow_up_enhancements": follow_up_enhancements,
        "confidence_guidance": confidence_guidance,
        "next_follow_up_plan": next_plan,
    }

    out_path = Path(args.out or _default_out_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    md_path = Path(args.out_md) if args.out_md else out_path.with_suffix(".md")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        _render_markdown_summary(
            scenario=args.scenario,
            summary=out_payload["summary"],
            checks=checks,
            follow_up_enhancements=follow_up_enhancements,
            scenario_database=out_payload["scenario_database"],
        ),
        encoding="utf-8",
    )

    print(json.dumps(out_payload["summary"], sort_keys=True))
    return 0 if out_payload["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
