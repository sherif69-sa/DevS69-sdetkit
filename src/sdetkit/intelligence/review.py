from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import doctor, inspect_project, readiness
from ..evidence_workspace import load_workspace_manifest, record_workspace_run
from ..inspect_compare import run_compare
from ..inspect_data import run_inspect
from ..security import SecurityError, safe_path
from .judgment import build_judgment, load_latest_previous_payload
from .review_engine import (
    apply_probe_memory_update,
    apply_probe_result_feedback,
    build_contradiction_clusters,
    build_staged_plan,
    build_typed_evidence_edges,
    decide_escalation,
    decide_stop,
    investigation_confidence,
    normalize_probe_execution_outcomes,
    plan_adaptive_probes,
    profile_confidence_level,
    profile_priority_tier,
    profile_weighted_priority,
    rank_likely_issue_tracks,
    summarize_history_delta,
)

SCHEMA_VERSION = "sdetkit.review.v3"
REVIEW_CONTRACT_VERSION = "sdetkit.review.contract.v1"
EXIT_OK = 0
EXIT_FINDINGS = 2
UTC = getattr(_dt, "UTC", _dt.timezone.utc)  # noqa: UP017
datetime = _dt.datetime
timedelta = _dt.timedelta


@dataclass(frozen=True)
class ReviewProfile:
    name: str
    summary_style: str
    max_text_matters: int
    doctor_weight: float
    inspect_weight: float
    compare_weight: float
    inspect_project_weight: float
    contradiction_weight: int
    urgency_now_threshold: int
    urgency_next_threshold: int
    fail_threshold: int
    watch_threshold: int
    contradiction_fail_count: int
    contradiction_watch_count: int
    confidence_high: float
    confidence_medium: float


@dataclass(frozen=True)
class ReviewStage:
    name: str
    checks: tuple[str, ...]
    intent: str


REVIEW_PROFILES: dict[str, ReviewProfile] = {
    "release": ReviewProfile(
        name="release",
        summary_style="release-gate",
        max_text_matters=5,
        doctor_weight=1.25,
        inspect_weight=1.0,
        compare_weight=1.0,
        inspect_project_weight=1.1,
        contradiction_weight=18,
        urgency_now_threshold=65,
        urgency_next_threshold=35,
        fail_threshold=60,
        watch_threshold=30,
        contradiction_fail_count=1,
        contradiction_watch_count=1,
        confidence_high=0.75,
        confidence_medium=0.45,
    ),
    "triage": ReviewProfile(
        name="triage",
        summary_style="triage-board",
        max_text_matters=3,
        doctor_weight=0.9,
        inspect_weight=1.15,
        compare_weight=0.8,
        inspect_project_weight=1.0,
        contradiction_weight=12,
        urgency_now_threshold=75,
        urgency_next_threshold=45,
        fail_threshold=72,
        watch_threshold=42,
        contradiction_fail_count=2,
        contradiction_watch_count=1,
        confidence_high=0.8,
        confidence_medium=0.55,
    ),
    "forensics": ReviewProfile(
        name="forensics",
        summary_style="evidence-ledger",
        max_text_matters=7,
        doctor_weight=0.85,
        inspect_weight=1.25,
        compare_weight=1.35,
        inspect_project_weight=1.15,
        contradiction_weight=25,
        urgency_now_threshold=55,
        urgency_next_threshold=25,
        fail_threshold=52,
        watch_threshold=24,
        contradiction_fail_count=1,
        contradiction_watch_count=1,
        confidence_high=0.85,
        confidence_medium=0.6,
    ),
    "monitor": ReviewProfile(
        name="monitor",
        summary_style="signal-watch",
        max_text_matters=4,
        doctor_weight=0.8,
        inspect_weight=0.95,
        compare_weight=1.2,
        inspect_project_weight=0.9,
        contradiction_weight=10,
        urgency_now_threshold=80,
        urgency_next_threshold=55,
        fail_threshold=82,
        watch_threshold=40,
        contradiction_fail_count=2,
        contradiction_watch_count=1,
        confidence_high=0.7,
        confidence_medium=0.4,
    ),
}

BASELINE_STAGES: tuple[ReviewStage, ...] = (
    ReviewStage(
        name="layer-1-baseline",
        checks=("doctor", "inspect", "inspect-project"),
        intent="Collect baseline signals quickly across repo, data, and policy surfaces.",
    ),
    ReviewStage(
        name="layer-2-deepen",
        checks=("inspect-compare", "workspace-history"),
        intent="Deepen investigation only when the baseline contains risk, drift, or contradictions.",
    ),
)


def _sorted_findings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [item for item in items if isinstance(item, dict)]
    return sorted(
        ranked,
        key=lambda item: (
            -int(item.get("priority", 0)),
            str(item.get("kind", "")),
            str(item.get("id", "")),
        ),
    )


def _profile_packet_filename(profile_name: str) -> str:
    if profile_name == "release":
        return "release-decision.json"
    if profile_name == "triage":
        return "incident-board.json"
    if profile_name == "forensics":
        return "evidence-ledger.json"
    return "trend-watch.json"


def _build_profile_packet(payload: dict[str, Any]) -> dict[str, Any]:
    profile = str(payload.get("profile", {}).get("name", "release"))
    findings = _sorted_findings(
        [item for item in payload.get("top_matters", []) if isinstance(item, dict)]
    )
    contradictions = _sorted_findings(
        [item for item in payload.get("conflicting_evidence", []) if isinstance(item, dict)]
    )
    now_actions = [
        item
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict) and str(item.get("tier")) == "now"
    ]
    next_actions = [
        item
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict) and str(item.get("tier")) == "next"
    ]
    monitor_actions = [
        item
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict) and str(item.get("tier")) == "monitor"
    ]
    changed = [item for item in payload.get("changed_since_previous", []) if isinstance(item, dict)]
    healthy_controls = [str(item) for item in payload.get("healthy_controls", [])]
    status = str(payload.get("status", "pass"))

    if profile == "release":
        blockers = [item for item in findings if int(item.get("priority", 0)) >= 60]
        return {
            "packet_type": "release_gate",
            "profile": "release",
            "decision": "block" if status == "fail" else ("watch" if status == "watch" else "ship"),
            "decision_rationale": {
                "status": status,
                "severity": payload.get("severity"),
                "blocking_findings_count": len(blockers),
                "contradictions_count": len(contradictions),
            },
            "controls": {
                "healthy_controls": healthy_controls,
                "source_workflows_run": payload.get("source_workflows_run", []),
            },
            "blockers": blockers,
            "now_actions": now_actions,
        }
    if profile == "triage":
        board_items = findings[:5]
        return {
            "packet_type": "incident_board",
            "profile": "triage",
            "board_status": status,
            "top_incidents": board_items,
            "sort_queue": {
                "now": now_actions[:5],
                "next": next_actions[:5],
            },
            "verification_queue": contradictions[:5],
            "snapshot": {
                "findings_count": len(findings),
                "contradictions_count": len(contradictions),
                "healthy_controls_count": len(healthy_controls),
            },
        }
    if profile == "forensics":
        return {
            "packet_type": "evidence_ledger",
            "profile": "forensics",
            "ledger_status": status,
            "supporting_evidence": payload.get("supporting_evidence", []),
            "conflicting_evidence": contradictions,
            "contradiction_matrix": [
                {
                    "id": str(item.get("id", "")),
                    "kind": str(item.get("kind", "")),
                    "priority": int(item.get("priority", 0)),
                    "message": str(item.get("message", "")),
                }
                for item in contradictions
            ],
            "historical_deltas": changed,
            "prioritized_actions": {
                "now": now_actions,
                "next": next_actions,
                "monitor": monitor_actions,
            },
            "findings": findings,
        }
    return {
        "packet_type": "trend_watch",
        "profile": "monitor",
        "watch_status": status,
        "trend_signals": changed,
        "watchlist": {
            "active_findings": findings[:8],
            "monitor_actions": monitor_actions[:8],
        },
        "continuity": {
            "has_previous_review": payload.get("history", {}).get("has_previous_review", False),
            "previous_review_run_hash": payload.get("history", {}).get("previous_review_run_hash"),
            "workspace_runs": [
                item
                for item in payload.get("supporting_evidence", [])
                if item.get("kind") == "workspace_runs"
            ],
        },
        "volatility_flags": contradictions,
    }


def _safe_slug(value: str) -> str:
    out: list[str] = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "review"


def _load_json(path: Path) -> dict[str, Any]:
    candidate = safe_path(Path.cwd(), path.as_posix(), allow_absolute=True).resolve()
    if not candidate.exists() or not candidate.is_file():
        raise ValueError(f"review: expected readable file at {candidate}")
    loaded = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"review: expected JSON object at {candidate}")
    return loaded


def _summarize_code_scanning(path: Path) -> dict[str, Any]:
    loaded = _load_json(path)
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
    total = 0
    tool = "generic"
    schema = "generic-json"
    alerts: list[dict[str, Any]] = []
    if isinstance(loaded.get("runs"), list):
        schema = "sarif"
        for run in loaded["runs"]:
            if not isinstance(run, dict):
                continue
            driver = run.get("tool", {}).get("driver", {})
            if isinstance(driver, dict) and driver.get("name"):
                tool = str(driver.get("name"))
            for result in (
                run.get("results", []) if isinstance(run.get("results", []), list) else []
            ):
                if not isinstance(result, dict):
                    continue
                level = str(result.get("level", "warning")).lower()
                if level == "error":
                    sev = "high"
                elif level in {"warning", "warn"}:
                    sev = "medium"
                elif level in {"note", "info"}:
                    sev = "low"
                else:
                    sev = "unknown"
                by_severity[sev] += 1
                total += 1
                alerts.append({"severity": sev, "rule_id": str(result.get("ruleId", ""))})
    else:
        raw_alerts = loaded.get("alerts", [])
        if isinstance(raw_alerts, list):
            for row in raw_alerts:
                if not isinstance(row, dict):
                    continue
                sev = str(row.get("severity", "unknown")).lower()
                if sev not in by_severity:
                    sev = "unknown"
                by_severity[sev] += 1
                total += 1
                alerts.append({"severity": sev, "rule_id": str(row.get("rule_id", ""))})
    blocking = by_severity["critical"] + by_severity["high"]
    return {
        "schema_version": "sdetkit.review.code-scanning.v1",
        "source": path.as_posix(),
        "format": schema,
        "tool": tool,
        "total_alerts": total,
        "blocking_alerts": blocking,
        "by_severity": by_severity,
        "sample_alerts": alerts[:10],
    }


def _probe_memory_path(*, workspace_root: Path, scope: str) -> Path:
    return workspace_root / "probe-memory" / "review" / f"{_safe_slug(scope)}.json"


def _load_probe_memory(*, workspace_root: Path, scope: str) -> dict[str, Any]:
    default = {"schema_version": "sdetkit.review.probe-memory.v1", "probes": {}}
    path = _probe_memory_path(workspace_root=workspace_root, scope=scope)
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(loaded, dict):
        return default
    probes = loaded.get("probes", {})
    loaded["probes"] = probes if isinstance(probes, dict) else {}
    loaded["schema_version"] = "sdetkit.review.probe-memory.v1"
    return loaded


def _write_probe_memory(*, workspace_root: Path, scope: str, memory: dict[str, Any]) -> str:
    path = _probe_memory_path(workspace_root=workspace_root, scope=scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path.as_posix()


def _finalize_probe_lifecycle(adaptive_plan: dict[str, Any]) -> None:
    executed_rows = adaptive_plan.get("executed_probes", [])
    skipped_rows = adaptive_plan.get("skipped_probes", [])
    executed_out: list[dict[str, Any]] = []
    skipped_out: list[dict[str, Any]] = []
    skipped_ids: set[str] = set()
    for row in executed_rows if isinstance(executed_rows, list) else []:
        if not isinstance(row, dict):
            continue
        probe_id = str(row.get("probe_id", ""))
        if str(row.get("status", "")) == "executed":
            executed_out.append(row)
            skipped_ids.add(probe_id)
            continue
        moved = dict(row)
        moved["status"] = "skipped"
        moved["skip_reason"] = (
            str(row.get("skip_reason", "")) or "probe planned but not executed in deepen stage"
        )
        if probe_id and probe_id in skipped_ids:
            continue
        skipped_out.append(moved)
        if probe_id:
            skipped_ids.add(probe_id)
    for row in skipped_rows if isinstance(skipped_rows, list) else []:
        if not isinstance(row, dict):
            continue
        probe_id = str(row.get("probe_id", ""))
        if probe_id and probe_id in skipped_ids:
            continue
        skipped_out.append(row)
        if probe_id:
            skipped_ids.add(probe_id)
    executed_out = sorted(executed_out, key=lambda item: str(item.get("probe_id", "")))
    skipped_out = sorted(skipped_out, key=lambda item: str(item.get("probe_id", "")))
    adaptive_plan["executed_probes"] = executed_out
    adaptive_plan["skipped_probes"] = skipped_out


def _detect_mode(target: Path) -> dict[str, bool]:
    is_dir = target.is_dir()
    repo_like = is_dir and ((target / ".git").exists() or (target / "pyproject.toml").exists())
    policy_project = is_dir and (target / "inspect-project.json").exists()
    data_like = False
    if target.is_file() and target.suffix.lower() in {".csv", ".json"}:
        data_like = True
    elif is_dir:
        data_files = [
            p
            for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in {".csv", ".json"} and ".sdetkit" not in p.parts
        ]
        data_like = bool(data_files)
    workspace_like = is_dir and ((target / ".sdetkit" / "workspace" / "manifest.json").exists())
    return {
        "repo_like": repo_like,
        "policy_project": policy_project,
        "data_like": data_like,
        "workspace_like": workspace_like,
    }


def _coerce_profile(name: str) -> ReviewProfile:
    normalized = name.strip().lower()
    if normalized not in REVIEW_PROFILES:
        valid = ", ".join(sorted(REVIEW_PROFILES))
        raise ValueError(f"review: unsupported profile '{name}'. expected one of: {valid}")
    return REVIEW_PROFILES[normalized]


def _workflows_for_profile(detection: dict[str, bool], profile: ReviewProfile) -> dict[str, bool]:
    run_doctor = detection["repo_like"] and profile.name in {"release", "triage", "monitor"}
    run_inspect = detection["data_like"] and not detection["policy_project"]
    run_project = detection["policy_project"]
    run_compare = run_inspect and profile.name in {"release", "forensics", "monitor"}
    run_history = detection["workspace_like"] or profile.name in {"monitor", "forensics"}
    return {
        "doctor": run_doctor,
        "inspect": run_inspect,
        "inspect_project": run_project,
        "inspect_compare": run_compare,
        "workspace_history": run_history,
    }


def _run_doctor(
    target: Path, out_dir: Path, workspace_root: Path, no_workspace: bool
) -> tuple[int, dict[str, Any], Path]:
    doctor_json = out_dir / "doctor.json"
    args = [
        "--json",
        "--repo",
        "--ci",
        "--deps",
        "--clean-tree",
        "--workspace-root",
        str(workspace_root),
        "--out",
        str(doctor_json),
    ]
    if no_workspace:
        args.append("--no-workspace")
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    # doctor operates on cwd repo state.
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        try:
            rc = doctor.main(args)
        except SystemExit as exc:
            rc = int(exc.code) if isinstance(exc.code, int) else 1
    payload = _load_json(doctor_json)
    return int(rc), payload, doctor_json


def _run_readiness(target: Path, out_dir: Path) -> tuple[dict[str, Any], Path]:
    readiness_root = target if target.is_dir() else target.parent
    payload = readiness.build_readiness_report(readiness_root)
    readiness_json = out_dir / "readiness.json"
    readiness_json.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload, readiness_json


def _review_scope_for_target(target: Path) -> str:
    return _safe_slug(target.resolve().as_posix())


def run_review(
    *,
    target: Path,
    out_dir: Path,
    workspace_root: Path,
    profile: str = "release",
    no_workspace: bool = False,
    work_id: str | None = None,
    work_context: dict[str, str] | None = None,
    code_scan_json: Path | None = None,
) -> tuple[int, dict[str, Any], Path, Path]:
    try:
        target = safe_path(Path.cwd(), target.as_posix(), allow_absolute=True).resolve()
        out_dir = safe_path(Path.cwd(), out_dir.as_posix(), allow_absolute=True)
        workspace_root = safe_path(Path.cwd(), workspace_root.as_posix(), allow_absolute=True)
        if code_scan_json is not None:
            scan_root = target if target.is_dir() else target.parent
            if code_scan_json.is_absolute() or len(code_scan_json.parts) != 1:
                raise ValueError("review: code scanning file must be a single relative file name")
            code_scan_json = safe_path(scan_root, code_scan_json.name, allow_absolute=False)
            scan_root_real = scan_root.resolve()
            code_scan_real = code_scan_json.resolve()
            if code_scan_real != scan_root_real and scan_root_real not in code_scan_real.parents:
                raise ValueError("review: code scanning file escapes scan root")
            code_scan_json = code_scan_real
    except SecurityError as exc:
        raise ValueError(f"review: path rejected: {exc}") from exc
    if not target.exists():
        raise ValueError(f"review: path does not exist: {target}")

    detection = _detect_mode(target)
    selected_profile = _coerce_profile(profile)
    workflow_plan = _workflows_for_profile(detection, selected_profile)
    review_scope = _review_scope_for_target(target)
    out_dir.mkdir(parents=True, exist_ok=True)
    probe_memory = (
        _load_probe_memory(workspace_root=workspace_root, scope=review_scope)
        if not no_workspace
        else {
            "schema_version": "sdetkit.review.probe-memory.v1",
            "probes": {},
        }
    )
    previous_review = None
    previous_hash = None
    if not no_workspace:
        previous_review, previous_hash = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="review",
            scope=review_scope,
        )

    source_workflows: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    conflicting: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    healthy_controls: list[str] = []
    prioritized_actions: list[dict[str, Any]] = []
    artifact_index: dict[str, str] = {}
    adaptive_plan = build_staged_plan(
        profile_name=selected_profile.name,
        stages=BASELINE_STAGES,
        workflow_plan=workflow_plan,
    )
    baseline_stage = adaptive_plan["stages"][0]
    deepen_stage = adaptive_plan["stages"][1]
    baseline_checks = list(baseline_stage.get("checks_planned", []))
    code_scanning_summary: dict[str, Any] | None = None
    if code_scan_json is not None:
        if not code_scan_json.exists():
            raise ValueError(f"review: code scanning file does not exist: {code_scan_json}")
        if not code_scan_json.is_file():
            raise ValueError(f"review: code scanning path must be a file: {code_scan_json}")
        code_scanning_summary = _summarize_code_scanning(code_scan_json)
        artifact_index["code_scan_json"] = code_scan_json.as_posix()
        supporting.append(
            {"kind": "code_scanning_alerts_total", "value": code_scanning_summary["total_alerts"]}
        )
        supporting.append(
            {
                "kind": "code_scanning_blocking_alerts",
                "value": code_scanning_summary["blocking_alerts"],
            }
        )
        if int(code_scanning_summary["blocking_alerts"]) > 0:
            findings.append(
                {
                    "id": "review:code-scanning",
                    "kind": "code-scanning",
                    "severity": "high",
                    "priority": 75,
                    "why_it_matters": "code scanning reported blocking security alerts",
                    "next_action": "Fix or explicitly triage blocking code scanning alerts.",
                    "message": (
                        f"code scanning found {code_scanning_summary['blocking_alerts']} "
                        "blocking alert(s)"
                    ),
                }
            )
            prioritized_actions.append(
                {
                    "tier": "now",
                    "priority": 75,
                    "action": "Resolve high/critical code scanning alerts before promotion.",
                }
            )
        else:
            healthy_controls.append("code scanning reports no high/critical alerts")

    if "doctor" in baseline_checks:
        doctor_out = out_dir / "doctor"
        doctor_out.mkdir(parents=True, exist_ok=True)
        prev_cwd = Path.cwd()
        try:
            if target.is_dir():
                import os

                os.chdir(target)
            doctor_rc, doctor_payload, doctor_json = _run_doctor(
                target,
                doctor_out,
                workspace_root,
                no_workspace,
            )
        finally:
            import os

            os.chdir(prev_cwd)
        artifact_index["doctor_json"] = doctor_json.as_posix()
        doctor_status = "ok" if doctor_rc == 0 else "findings"
        source_workflows.append({"workflow": "doctor", "status": doctor_status})
        baseline_stage["checks_run"].append({"check": "doctor", "status": doctor_status})
        if doctor_rc == 0:
            healthy_controls.append("doctor checks passed for repo hygiene and release controls")
        else:
            findings.append(
                {
                    "id": "review:doctor",
                    "kind": "doctor",
                    "severity": "high",
                    "priority": 70,
                    "why_it_matters": "doctor reported repo-level release risks",
                    "next_action": "Address failing doctor checks before promotion decisions.",
                    "message": "doctor reported findings",
                }
            )
            prioritized_actions.append(
                {
                    "tier": "now",
                    "priority": 70,
                    "action": "Fix doctor failures in repo governance and hygiene checks.",
                }
            )
        supporting.append({"kind": "doctor_ok", "value": bool(doctor_payload.get("ok", False))})

    if detection["repo_like"]:
        readiness_payload, readiness_json = _run_readiness(target, out_dir)
        artifact_index["readiness_json"] = readiness_json.as_posix()
        readiness_score = float(readiness_payload.get("score", 0.0))
        readiness_tier = str(readiness_payload.get("tier", "needs-work"))
        readiness_status = "ok" if readiness_score >= 75.0 else "findings"
        source_workflows.append({"workflow": "readiness", "status": readiness_status})
        baseline_stage["checks_run"].append({"check": "readiness", "status": readiness_status})
        supporting.append({"kind": "readiness_score", "value": readiness_score})
        supporting.append({"kind": "readiness_tier", "value": readiness_tier})
        supporting.append(
            {
                "kind": "readiness_operational_tier",
                "value": str(readiness_payload.get("operational_tier", "needs-work")),
            }
        )
        supporting.append(
            {
                "kind": "readiness_top_tier_ready",
                "value": bool(readiness_payload.get("top_tier_ready", False)),
            }
        )
        supporting.append(
            {
                "kind": "readiness_check_scorecard",
                "value": dict(readiness_payload.get("check_scorecard", {})),
            }
        )
        supporting.append(
            {
                "kind": "readiness_failed_checks",
                "value": list(readiness_payload.get("failed_checks", [])),
            }
        )
        supporting.append(
            {
                "kind": "readiness_scenario_capacity",
                "value": dict(readiness_payload.get("scenario_capacity", {})),
            }
        )

        if readiness_score >= 90.0:
            healthy_controls.append(
                "production-readiness scorecard indicates strong launch posture"
            )
        else:
            findings.append(
                {
                    "id": "review:readiness",
                    "kind": "readiness",
                    "severity": "high" if readiness_score < 75.0 else "medium",
                    "priority": 72 if readiness_score < 75.0 else 58,
                    "why_it_matters": (
                        "readiness scorecard indicates missing launch controls across governance/CI/release"
                    ),
                    "next_action": "Close top readiness actions before promotion decisions.",
                    "message": f"readiness score is {readiness_score} ({readiness_tier})",
                }
            )
            for idx, action in enumerate(readiness_payload.get("adaptive_actions", [])[:3]):
                if not isinstance(action, dict):
                    continue
                prioritized_actions.append(
                    {
                        "tier": str(
                            action.get("lane", "now" if readiness_score < 75.0 else "next")
                        ),
                        "priority": int(action.get("priority", 72 - idx)),
                        "action": str(action.get("action", "")),
                    }
                )

    inspect_payload: dict[str, Any] | None = None
    if "inspect" in baseline_checks:
        inspect_out = out_dir / "inspect"
        inspect_rc, inspect_payload, inspect_json_path, inspect_txt_path = run_inspect(
            input_path=target,
            out_dir=inspect_out,
            workspace_root=workspace_root,
            record_workspace=not no_workspace,
            workspace_scope=_review_scope_for_target(target),
        )
        artifact_index["inspect_json"] = inspect_json_path.as_posix()
        artifact_index["inspect_txt"] = inspect_txt_path.as_posix()
        inspect_status = "ok" if inspect_rc == 0 else "findings"
        source_workflows.append({"workflow": "inspect", "status": inspect_status})
        baseline_stage["checks_run"].append({"check": "inspect", "status": inspect_status})
        supporting.append(
            {
                "kind": "inspect_files",
                "value": inspect_payload.get("summary", {}).get("files_analyzed", 0),
            }
        )
        if inspect_rc == 0:
            healthy_controls.append("inspect evidence diagnostics are stable")
        else:
            findings.append(
                {
                    "id": "review:inspect",
                    "kind": "inspect",
                    "severity": "high",
                    "priority": 65,
                    "why_it_matters": "inspect surfaced suspicious evidence or rule failures",
                    "next_action": "Investigate inspect anomalies and resolve suspicious signals.",
                    "message": "inspect reported findings",
                }
            )
            prioritized_actions.append(
                {
                    "tier": "now",
                    "priority": 65,
                    "action": "Resolve inspect evidence anomalies and rerun review.",
                }
            )

    if "inspect-project" in baseline_checks:
        project_out = out_dir / "inspect-project"
        rc = inspect_project.main(
            [
                str(target),
                "--workspace-root",
                str(workspace_root),
                "--out-dir",
                str(project_out),
                "--format",
                "json",
                *(["--no-workspace"] if no_workspace else []),
            ]
        )
        project_payload = _load_json(project_out / "inspect-project.json")
        artifact_index["inspect_project_json"] = (project_out / "inspect-project.json").as_posix()
        artifact_index["inspect_project_txt"] = (project_out / "inspect-project.txt").as_posix()
        project_status = "ok" if rc == 0 else "findings"
        source_workflows.append({"workflow": "inspect-project", "status": project_status})
        baseline_stage["checks_run"].append({"check": "inspect-project", "status": project_status})
        supporting.append(
            {
                "kind": "inspect_project_scopes",
                "value": project_payload.get("summary", {}).get("scopes", 0),
            }
        )
        if rc != 0:
            findings.append(
                {
                    "id": "review:inspect-project",
                    "kind": "inspect-project",
                    "severity": "high",
                    "priority": 60,
                    "why_it_matters": "inspect-project policy pack found high-signal scope risks",
                    "next_action": "Remediate failing scopes in inspect-project outputs.",
                    "message": "inspect-project reported findings",
                }
            )

    # contradictions as first-class product output (baseline signal set)
    contradiction_graph = build_contradiction_clusters(findings=findings, detection=detection)
    conflicting.extend(contradiction_graph.get("flat_contradictions", []))

    baseline_confidence = investigation_confidence(
        source_workflows=source_workflows,
        findings=findings,
        conflicts=conflicting,
    )
    escalation = decide_escalation(
        findings=findings,
        conflicts=conflicting,
        baseline_confidence=baseline_confidence,
        confidence_threshold=selected_profile.confidence_medium,
        force_deepen=selected_profile.name == "forensics",
    )
    adaptive_plan["escalation"] = escalation.as_dict()
    deepen_checks = list(deepen_stage.get("checks_planned", []))
    deepen_stage["ran"] = escalation.needed
    probe_decision = plan_adaptive_probes(
        detection=detection,
        profile_name=selected_profile.name,
        findings=findings,
        contradiction_graph=contradiction_graph,
        has_previous_review=False,
        changed=[],
        confidence_score=baseline_confidence,
        confidence_threshold=selected_profile.confidence_medium,
        probe_memory=probe_memory,
    )
    adaptive_plan["executed_probes"] = probe_decision["executed_probes"]
    adaptive_plan["skipped_probes"] = probe_decision["skipped_probes"]
    adaptive_plan["probe_registry"] = probe_decision["registry"]
    adaptive_plan["probe_budget"] = probe_decision["budget"]
    adaptive_plan["ai_assistant"] = probe_decision["ai_assistant"]

    if (
        inspect_payload
        and "inspect-compare" in deepen_checks
        and escalation.needed
        and (
            not previous_review
            or not detection.get("repo_like", False)
            or bool(contradiction_graph.get("flat_contradictions"))
        )
        and not no_workspace
    ):
        scope = _review_scope_for_target(target)
        previous_inspect, _ = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="inspect",
            scope=scope,
        )
        if isinstance(previous_inspect, dict):
            compare_out = out_dir / "inspect-compare"
            compare_rc, compare_payload, compare_json, compare_txt = run_compare(
                left_payload=previous_inspect,
                right_payload=inspect_payload,
                left_label="workspace:previous",
                right_label="workspace:current",
                out_dir=compare_out,
                out_scope=scope,
                workspace_root=workspace_root,
                record_workspace=not no_workspace,
            )
            artifact_index["inspect_compare_json"] = compare_json.as_posix()
            artifact_index["inspect_compare_txt"] = compare_txt.as_posix()
            source_workflows.append(
                {"workflow": "inspect-compare", "status": "ok" if compare_rc == 0 else "findings"}
            )
            deepen_stage["checks_run"].append(
                {"check": "inspect-compare", "status": "ok" if compare_rc == 0 else "findings"}
            )
            drift_score = int(compare_payload.get("summary", {}).get("drift_score", 0))
            supporting.append({"kind": "drift_score", "value": drift_score})
            if compare_rc != 0:
                findings.append(
                    {
                        "id": "review:inspect-compare",
                        "kind": "inspect-compare",
                        "severity": "medium",
                        "priority": min(55, 20 + drift_score * 4),
                        "why_it_matters": "recent evidence drift changed baseline behavior",
                        "next_action": "Review drift files and approve intended changes.",
                        "message": "inspect-compare detected drift",
                    }
                )
            for row in adaptive_plan.get("executed_probes", []):
                if isinstance(row, dict) and row.get("probe_id") == "probe:inspect-compare":
                    row["status"] = "executed"
                    row["result"] = "findings" if compare_rc != 0 else "ok"

    if "workspace-history" in deepen_checks and escalation.needed and detection["workspace_like"]:
        manifest = load_workspace_manifest(target / ".sdetkit" / "workspace")
        supporting.append({"kind": "workspace_runs", "value": len(manifest.get("runs", []))})
        source_workflows.append({"workflow": "workspace-history", "status": "ok"})
        deepen_stage["checks_run"].append({"check": "workspace-history", "status": "ok"})
        for row in adaptive_plan.get("executed_probes", []):
            if isinstance(row, dict) and row.get("probe_id") == "probe:workspace-history":
                row["status"] = "executed"
                row["result"] = "ok"

    weighted_findings = [
        {**item, "priority": profile_weighted_priority(item, selected_profile)} for item in findings
    ]
    weighted_conflicts = [
        {
            **item,
            "priority": selected_profile.contradiction_weight,
        }
        for item in conflicting
    ]
    contradiction_count = len(conflicting)
    contradiction_boost = contradiction_count * selected_profile.contradiction_weight
    effective_max_priority = (
        max([0, *(int(item.get("priority", 0)) for item in weighted_findings)])
        + contradiction_boost
    )
    completeness = min(1.0, max(0.2, len(source_workflows) / 5.0))
    stability = 0.7 if conflicting else 0.85
    workflow_ok = len(weighted_findings) == 0
    blocking = (
        effective_max_priority >= selected_profile.fail_threshold
        or contradiction_count >= selected_profile.contradiction_fail_count
    )

    review_judgment = build_judgment(
        workflow="review",
        findings=weighted_findings,
        supporting_evidence=supporting,
        conflicting_evidence=weighted_conflicts,
        completeness=completeness,
        stability=stability,
        previous_summary=None,
        workflow_ok=workflow_ok,
        blocking=blocking,
    )
    if (
        effective_max_priority >= selected_profile.fail_threshold
        or contradiction_count >= selected_profile.contradiction_fail_count
    ):
        profile_status = "fail"
    elif (
        effective_max_priority >= selected_profile.watch_threshold
        or contradiction_count >= selected_profile.contradiction_watch_count
    ):
        profile_status = "watch"
    else:
        profile_status = "pass"
    profile_severity = "low"
    if profile_status == "watch":
        profile_severity = "medium"
    if profile_status == "fail":
        profile_severity = "high"
    review_judgment["status"] = profile_status
    review_judgment["severity"] = profile_severity
    review_judgment["profile"] = selected_profile.name
    review_judgment["profile_thresholds"] = {
        "fail_threshold": selected_profile.fail_threshold,
        "watch_threshold": selected_profile.watch_threshold,
        "contradiction_fail_count": selected_profile.contradiction_fail_count,
        "contradiction_watch_count": selected_profile.contradiction_watch_count,
        "effective_max_priority": effective_max_priority,
    }
    confidence = dict(review_judgment.get("confidence", {}))
    confidence["level"] = profile_confidence_level(
        float(confidence.get("score", 0.0)), selected_profile
    )
    confidence["profile_thresholds"] = {
        "high": selected_profile.confidence_high,
        "medium": selected_profile.confidence_medium,
    }
    review_judgment["confidence"] = confidence
    profile_recs: list[dict[str, Any]] = []
    for rec in review_judgment.get("recommendations", []):
        if not isinstance(rec, dict):
            continue
        priority = int(rec.get("priority", 0))
        profile_recs.append({**rec, "tier": profile_priority_tier(priority, selected_profile)})
    review_judgment["recommendations"] = profile_recs

    prioritized_actions.extend(review_judgment.get("recommendations", []))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": REVIEW_CONTRACT_VERSION,
        "tool": "sdetkit",
        "workflow": "review",
        "profile": {
            "name": selected_profile.name,
            "summary_style": selected_profile.summary_style,
            "orchestration_depth": "deep"
            if selected_profile.name in {"release", "forensics"}
            else "focused",
            "workflow_plan": workflow_plan,
            "urgency_thresholds": {
                "now": selected_profile.urgency_now_threshold,
                "next": selected_profile.urgency_next_threshold,
            },
        },
        "path": target.as_posix(),
        "status": review_judgment.get("status"),
        "severity": review_judgment.get("severity"),
        "confidence": review_judgment.get("confidence", {}),
        "review_status": "PASS" if workflow_ok else "ATTENTION",
        "top_matters": review_judgment.get("top_judgment", {}).get("what_matters_most", []),
        "supporting_evidence": supporting,
        "conflicting_evidence": weighted_conflicts,
        "healthy_controls": healthy_controls,
        "changed_since_previous": [],
        "prioritized_actions": prioritized_actions[:8],
        "likely_issue_tracks": [],
        "source_workflows_run": source_workflows,
        "artifact_index": artifact_index,
        "adaptive_review": adaptive_plan,
        "judgment": review_judgment,
        "history": {
            "workspace_root": workspace_root.as_posix(),
            "has_previous_review": bool(previous_review),
            "previous_review_run_hash": previous_hash,
        },
        "detection": detection,
        "request_context": {
            "work_id": (work_id or "").strip(),
            "work_context": dict(work_context or {}),
        },
    }
    if code_scanning_summary is not None:
        payload["code_scanning"] = code_scanning_summary
    payload["changed_since_previous"] = summarize_history_delta(previous_review, payload)
    probe_decision = plan_adaptive_probes(
        detection=detection,
        profile_name=selected_profile.name,
        findings=weighted_findings,
        contradiction_graph=contradiction_graph,
        has_previous_review=bool(previous_review),
        changed=payload["changed_since_previous"],
        confidence_score=float(review_judgment.get("confidence", {}).get("score", 0.0)),
        confidence_threshold=selected_profile.confidence_medium,
        probe_memory=probe_memory,
    )
    existing_probe_results = {
        str(row.get("probe_id")): row
        for row in adaptive_plan.get("executed_probes", [])
        if isinstance(row, dict) and row.get("status") == "executed"
    }
    merged_executed: list[dict[str, Any]] = []
    for row in probe_decision["executed_probes"]:
        existing = existing_probe_results.get(str(row.get("probe_id")))
        merged_executed.append(existing if existing else row)
    adaptive_plan["executed_probes"] = merged_executed
    adaptive_plan["skipped_probes"] = probe_decision["skipped_probes"]
    adaptive_plan["probe_registry"] = probe_decision["registry"]
    adaptive_plan["probe_budget"] = probe_decision["budget"]
    adaptive_plan["ai_assistant"] = probe_decision["ai_assistant"]
    _finalize_probe_lifecycle(adaptive_plan)
    likely_tracks = rank_likely_issue_tracks(
        findings=weighted_findings,
        conflicts=weighted_conflicts,
        changed=payload["changed_since_previous"],
    )
    payload["likely_issue_tracks"] = likely_tracks
    payload["contradiction_graph"] = contradiction_graph
    probe_feedback = apply_probe_result_feedback(
        findings=weighted_findings,
        conflicts=weighted_conflicts,
        likely_tracks=likely_tracks,
        executed_probes=[
            row
            for row in adaptive_plan.get("executed_probes", [])
            if row.get("status") == "executed"
        ],
    )
    payload["adaptive_review"]["probe_feedback"] = probe_feedback
    payload["adaptive_review"]["probe_rationale"] = [
        {
            "probe_id": row.get("probe_id"),
            "why_chosen": row.get("reason"),
        }
        for row in adaptive_plan.get("executed_probes", [])
        if isinstance(row, dict)
    ]
    normalized_probe_outcomes = normalize_probe_execution_outcomes(
        executed_probes=[
            row for row in adaptive_plan.get("executed_probes", []) if isinstance(row, dict)
        ],
        findings=weighted_findings,
        conflicts=weighted_conflicts,
    )
    updated_probe_memory, probe_memory_update = apply_probe_memory_update(
        previous_memory=probe_memory,
        normalized_outcomes=normalized_probe_outcomes,
    )
    payload["adaptive_review"]["probe_memory"] = {
        "schema_version": updated_probe_memory.get("schema_version"),
        "normalized_outcomes": normalized_probe_outcomes,
        "updates": probe_memory_update.get("updates", []),
    }
    for update in probe_feedback.get("track_updates", []):
        if not isinstance(update, dict):
            continue
        for track in payload["likely_issue_tracks"]:
            if isinstance(track, dict) and track.get("track_id") == update.get("track_id"):
                track["likelihood"] = update.get("adjusted_likelihood", track.get("likelihood"))
                track["probe_impact"] = {
                    "base_likelihood": update.get("base_likelihood"),
                    "adjusted_likelihood": update.get("adjusted_likelihood"),
                }
                break
    payload["evidence_edges"] = build_typed_evidence_edges(
        executed_probes=[
            row for row in adaptive_plan.get("executed_probes", []) if isinstance(row, dict)
        ],
        conflicts=weighted_conflicts,
        findings=weighted_findings,
        tracks=payload["likely_issue_tracks"],
    )
    final_confidence = investigation_confidence(
        source_workflows=source_workflows,
        findings=weighted_findings,
        conflicts=weighted_conflicts,
    )
    final_confidence = round(
        max(0.0, min(1.0, final_confidence + float(probe_feedback.get("confidence_delta", 0.0)))), 2
    )
    adaptive_plan["stop_decision"] = decide_stop(
        final_confidence=final_confidence,
        confidence_threshold=selected_profile.confidence_medium,
        findings_count=len(weighted_findings),
        conflicts_count=len(weighted_conflicts),
    ).as_dict()
    profile_packet = _build_profile_packet(payload)
    payload["profile"]["packet_type"] = profile_packet["packet_type"]
    payload["profile"]["output_strategy"] = profile_packet["packet_type"]
    payload["profile_packet"] = profile_packet
    payload["five_heads"] = _build_five_head_engine(payload)
    top5_actions = [
        str(item.get("action", ""))
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict) and str(item.get("action", "")).strip()
    ][:5]
    workflow_alignment = {
        "doctor_included": any(
            isinstance(row, dict) and str(row.get("workflow")) == "doctor"
            for row in payload.get("source_workflows_run", [])
        ),
        "review_adaptive_enabled": True,
        "gate_fast_recommended": True,
        "code_scanning_included": "code_scanning" in payload,
        "readiness_included": "readiness_json" in artifact_index,
        "work_id": str(payload.get("request_context", {}).get("work_id", "")),
    }
    doctor_gate_contract = {
        "schema_version": "sdetkit.review.doctor-gate-contract.v1",
        "enforced_each_run": True,
        "doctor_first": True,
        "gate_fast_required_for_promotion": True,
        "canonical_sequence": [
            "python -m sdetkit doctor --format json",
            "python -m sdetkit readiness . --format json",
            "python -m sdetkit gate fast --format json --stable-json",
            "python -m sdetkit gate release --format json",
            "python -m sdetkit review . --format operator-json",
        ],
    }
    payload["doctor_gate_contract"] = doctor_gate_contract
    findings_severity_counts: dict[str, int] = {}
    findings_kind_counts: dict[str, int] = {}
    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity", "unknown"))
        kind = str(item.get("kind", "unknown"))
        findings_severity_counts[sev] = int(findings_severity_counts.get(sev, 0)) + 1
        findings_kind_counts[kind] = int(findings_kind_counts.get(kind, 0)) + 1

    action_tier_counts: dict[str, int] = {}
    for item in payload.get("prioritized_actions", []):
        if not isinstance(item, dict):
            continue
        tier = str(item.get("tier", "unknown"))
        action_tier_counts[tier] = int(action_tier_counts.get(tier, 0)) + 1

    release_blockers = [
        str(item.get("id", "unknown"))
        for item in payload.get("findings", [])
        if isinstance(item, dict) and int(item.get("priority", 0)) >= 70
    ]
    blocker_catalog: list[dict[str, Any]] = []
    owner_routing = {
        "doctor": ("platform-quality", 24),
        "readiness": ("release-management", 24),
        "code-scanning": ("security", 8),
        "inspect": ("qa-ops", 24),
        "inspect-project": ("qa-ops", 24),
    }
    for item in payload.get("findings", []):
        if not isinstance(item, dict) or int(item.get("priority", 0)) < 70:
            continue
        kind = str(item.get("kind", "unknown"))
        owner_team, response_sla_hours = owner_routing.get(kind, ("release-management", 24))
        blocker_catalog.append(
            {
                "id": str(item.get("id", "unknown")),
                "kind": kind,
                "severity": str(item.get("severity", "unknown")),
                "priority": int(item.get("priority", 0)),
                "why_it_matters": str(item.get("why_it_matters", "")),
                "next_action": str(item.get("next_action", "")),
                "owner_team": owner_team,
                "response_sla_hours": response_sla_hours,
            }
        )
    readiness_top_tier_ready = next(
        (
            bool(row.get("value", False))
            for row in supporting
            if isinstance(row, dict) and str(row.get("kind")) == "readiness_top_tier_ready"
        ),
        False,
    )
    if not readiness_top_tier_ready and "readiness:top-tier-gate" not in release_blockers:
        release_blockers.append("readiness:top-tier-gate")
        blocker_catalog.append(
            {
                "id": "readiness:top-tier-gate",
                "kind": "readiness",
                "severity": "high",
                "priority": 72,
                "why_it_matters": (
                    "Top-tier readiness gate is not satisfied for current scenario-capacity target."
                ),
                "next_action": "Close readiness adaptive actions until top_tier_ready=true.",
                "owner_team": "release-management",
                "response_sla_hours": 24,
            }
        )
    owner_summary_map: dict[str, dict[str, Any]] = {}
    for row in blocker_catalog:
        if not isinstance(row, dict):
            continue
        owner = str(row.get("owner_team", "release-management"))
        item = owner_summary_map.setdefault(
            owner,
            {
                "owner_team": owner,
                "blocker_count": 0,
                "max_priority": 0,
                "min_response_sla_hours": 72,
            },
        )
        item["blocker_count"] = int(item.get("blocker_count", 0)) + 1
        item["max_priority"] = max(int(item.get("max_priority", 0)), int(row.get("priority", 0)))
        item["min_response_sla_hours"] = min(
            int(item.get("min_response_sla_hours", 72)),
            int(row.get("response_sla_hours", 72)),
        )
    owner_summary = sorted(
        owner_summary_map.values(),
        key=lambda item: (-int(item.get("blocker_count", 0)), -int(item.get("max_priority", 0))),
    )
    owner_routes = [
        {
            "owner_team": str(item.get("owner_team", "")),
            "priority_focus": int(item.get("max_priority", 0)),
            "recommended_actions": [
                str(row.get("next_action", ""))
                for row in blocker_catalog
                if isinstance(row, dict)
                and str(row.get("owner_team", "")) == str(item.get("owner_team", ""))
                and str(row.get("next_action", "")).strip()
            ][:5],
        }
        for item in owner_summary
        if isinstance(item, dict)
    ]
    next_24h_actions = [
        str(item.get("action", ""))
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict)
        and str(item.get("tier", "")).strip().lower() == "now"
        and str(item.get("action", "")).strip()
    ][:5]
    next_72h_actions = [
        str(item.get("action", ""))
        for item in payload.get("prioritized_actions", [])
        if isinstance(item, dict)
        and str(item.get("tier", "")).strip().lower() in {"next", "soon"}
        and str(item.get("action", "")).strip()
    ][:8]
    release_ready_now = len(release_blockers) == 0
    generated_at = datetime.now(UTC)
    generated_at_utc = generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    next_review_due = generated_at + (
        timedelta(hours=72) if release_ready_now else timedelta(hours=24)
    )
    next_review_due_utc = next_review_due.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    contract_material = {
        "gate_decision": "ship" if release_ready_now else "hold",
        "blockers": release_blockers,
        "next_24h_actions": next_24h_actions,
        "next_72h_actions": next_72h_actions,
    }
    contract_id = hashlib.sha256(
        json.dumps(contract_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    previous_release_contract: dict[str, Any] | None = None
    if isinstance(previous_review, dict):
        prev_adaptive = previous_review.get("adaptive_database", {})
        if isinstance(prev_adaptive, dict):
            prev_contract = prev_adaptive.get("release_readiness_contract", {})
            if isinstance(prev_contract, dict):
                previous_release_contract = prev_contract

    prev_gate_decision = (
        str(previous_release_contract.get("gate_decision", "unknown"))
        if isinstance(previous_release_contract, dict)
        else "unknown"
    )
    prev_blockers_count = (
        len(previous_release_contract.get("blockers", []))
        if isinstance(previous_release_contract, dict)
        and isinstance(previous_release_contract.get("blockers", []), list)
        else 0
    )
    release_trend = {
        "has_previous_contract": bool(previous_release_contract),
        "previous_gate_decision": prev_gate_decision,
        "decision_changed": prev_gate_decision
        not in {"unknown", "ship" if release_ready_now else "hold"},
        "previous_blockers_count": prev_blockers_count,
        "current_blockers_count": len(release_blockers),
        "blockers_delta": len(release_blockers) - prev_blockers_count,
    }
    high_priority_findings = len(
        [
            row
            for row in payload.get("findings", [])
            if isinstance(row, dict) and int(row.get("priority", 0)) >= 70
        ]
    )
    release_risk_score = min(100, int((len(release_blockers) * 25) + (high_priority_findings * 10)))
    release_risk_band = (
        "critical"
        if release_risk_score >= 80
        else "high"
        if release_risk_score >= 55
        else "medium"
        if release_risk_score >= 30
        else "low"
    )
    sla_review_hours = (
        8
        if release_risk_band == "critical"
        else 24
        if release_risk_band == "high"
        else 48
        if release_risk_band == "medium"
        else 72
    )
    recommendation_engine = {
        "now": next_24h_actions[:5],
        "next_72h": next_72h_actions[:8],
        "watchlist": [
            str(item.get("action", ""))
            for item in payload.get("prioritized_actions", [])
            if isinstance(item, dict)
            and str(item.get("tier", "")).strip().lower() in {"monitor", "later"}
            and str(item.get("action", "")).strip()
        ][:8],
        "owner_routes": owner_routes,
    }
    backlog_candidates: list[tuple[str, str]] = []
    backlog_candidates.extend([("now", action) for action in recommendation_engine["now"]])
    backlog_candidates.extend([("next", action) for action in recommendation_engine["next_72h"]])
    backlog_candidates.extend([("watch", action) for action in recommendation_engine["watchlist"]])
    recommendation_backlog: list[dict[str, Any]] = []
    seen_actions: set[str] = set()
    for lane, action in backlog_candidates:
        normalized_action = str(action).strip()
        if not normalized_action or normalized_action in seen_actions:
            continue
        seen_actions.add(normalized_action)
        matched_blocker = next(
            (
                row
                for row in blocker_catalog
                if isinstance(row, dict)
                and str(row.get("next_action", "")).strip() == normalized_action
            ),
            {},
        )
        owner_team = (
            str(matched_blocker.get("owner_team", "release-management"))
            if isinstance(matched_blocker, dict)
            else "release-management"
        )
        urgency = 90 if lane == "now" else 65 if lane == "next" else 35
        impact = (
            85
            if release_risk_band in {"critical", "high"}
            else 70
            if release_risk_band == "medium"
            else 55
        )
        effort = 3 if len(normalized_action) < 80 else 5
        priority_index = round((impact + urgency) / max(effort, 1), 2)
        recommendation_backlog.append(
            {
                "action": normalized_action,
                "lane": lane,
                "owner_team": owner_team,
                "impact_score": impact,
                "urgency_score": urgency,
                "effort_score": effort,
                "priority_index": priority_index,
            }
        )
    recommendation_backlog.sort(
        key=lambda item: float(item.get("priority_index", 0.0)),
        reverse=True,
    )
    overall_engine = payload.get("five_heads", {}).get("overall", {})
    if not isinstance(overall_engine, dict):
        overall_engine = {}
    contradiction_clusters = payload.get("contradiction_graph", {}).get("clusters", [])
    if not isinstance(contradiction_clusters, list):
        contradiction_clusters = []
    executed_probes = payload.get("adaptive_review", {}).get("executed_probes", [])
    if not isinstance(executed_probes, list):
        executed_probes = []
    engine_signals = {
        "engine_score": float(overall_engine.get("score", 0.0)),
        "engine_status": str(overall_engine.get("status", "unknown")),
        "contradiction_clusters": len(contradiction_clusters),
        "executed_probes": len([row for row in executed_probes if isinstance(row, dict)]),
    }

    agent_orchestration: list[dict[str, Any]] = [
        {
            "agent_id": "release-ops-observer",
            "purpose": "Track release contract drift and artifact freshness across reruns.",
            "when_to_use": "Always during release week.",
            "engine_signals": engine_signals,
            "suggested_commands": [
                "python -m sdetkit review . --format operator-json",
                "python -m sdetkit review . --format json",
            ],
        }
    ]
    if release_risk_band in {"critical", "high"}:
        agent_orchestration.append(
            {
                "agent_id": "release-commander",
                "purpose": "Drive blocker burn-down and enforce ship/hold cadence.",
                "when_to_use": "High/critical release risk.",
                "engine_signals": engine_signals,
                "suggested_commands": [
                    "python -m sdetkit doctor --format json",
                    "python -m sdetkit gate release --format json",
                ],
            }
        )
    if any(
        str(item.get("id", "")).startswith("review:doctor")
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    ):
        agent_orchestration.append(
            {
                "agent_id": "platform-quality-agent",
                "purpose": "Resolve doctor hygiene/governance failures quickly.",
                "when_to_use": "Doctor findings present.",
                "engine_signals": engine_signals,
                "suggested_commands": [
                    "python -m sdetkit doctor --repo --ci --deps --clean-tree --format json",
                ],
            }
        )
    if "readiness:top-tier-gate" in release_blockers:
        agent_orchestration.append(
            {
                "agent_id": "readiness-hardening-agent",
                "purpose": "Close top-tier readiness gaps and scenario-capacity blockers.",
                "when_to_use": "Top-tier readiness gate fails.",
                "engine_signals": engine_signals,
                "suggested_commands": [
                    "python -m sdetkit readiness . --format json",
                ],
            }
        )
    if engine_signals["contradiction_clusters"] > 0 or engine_signals["executed_probes"] > 0:
        agent_orchestration.append(
            {
                "agent_id": "adaptive-probe-agent",
                "purpose": "Investigate contradiction clusters and tighten evidence confidence.",
                "when_to_use": "Contradiction clusters or probe-heavy runs detected.",
                "engine_signals": engine_signals,
                "suggested_commands": [
                    "python -m sdetkit inspect-compare --latest-vs-previous --format json",
                    "python -m sdetkit review . --format json",
                ],
            }
        )

    readiness_scenario_snapshot = next(
        (
            dict(row.get("value", {}))
            for row in supporting
            if isinstance(row, dict) and str(row.get("kind")) == "readiness_scenario_capacity"
        ),
        {"target_scenarios": 250, "detected_scenarios": 0, "gap": 250, "status": "needs-expansion"},
    )
    detected_scenarios = int(readiness_scenario_snapshot.get("detected_scenarios", 0))
    target_scenarios = int(readiness_scenario_snapshot.get("target_scenarios", 250))
    scenario_runway_ratio = (
        round((detected_scenarios / target_scenarios), 2) if target_scenarios else 0.0
    )
    readiness_failed_checks = next(
        (
            list(row.get("value", []))
            for row in supporting
            if isinstance(row, dict) and str(row.get("kind")) == "readiness_failed_checks"
        ),
        [],
    )
    canonical_aspects: tuple[str, ...] = (
        "governance_policy",
        "security_posture",
        "ci_quality",
        "test_capacity",
        "docs_operations",
        "dependency_hygiene",
        "release_management",
        "doctor_hygiene",
        "adaptive_reviewer_confidence",
        "scalability_readiness",
    )
    encountered_sources: dict[str, set[str]] = {aspect: set() for aspect in canonical_aspects}
    findings = [row for row in payload.get("findings", []) if isinstance(row, dict)]
    for finding in findings:
        kind = str(finding.get("kind", "")).lower()
        if "doctor" in kind:
            encountered_sources["doctor_hygiene"].add("finding.kind")
        if "security" in kind:
            encountered_sources["security_posture"].add("finding.kind")
        if "ci" in kind or "lint" in kind:
            encountered_sources["ci_quality"].add("finding.kind")
        if "release" in kind or "gate" in kind:
            encountered_sources["release_management"].add("finding.kind")
        if "readiness" in kind:
            encountered_sources["adaptive_reviewer_confidence"].add("finding.kind")
    for check_id in readiness_failed_checks:
        cid = str(check_id)
        if "security" in cid:
            encountered_sources["security_posture"].add("readiness.failed_check")
        if "release" in cid or "changelog" in cid:
            encountered_sources["release_management"].add("readiness.failed_check")
        if "dependency" in cid:
            encountered_sources["dependency_hygiene"].add("readiness.failed_check")
        if "test" in cid or "scenario" in cid:
            encountered_sources["test_capacity"].add("readiness.failed_check")
        if "docs" in cid:
            encountered_sources["docs_operations"].add("readiness.failed_check")
        if "governance" in cid:
            encountered_sources["governance_policy"].add("readiness.failed_check")
    if workflow_alignment["doctor_included"]:
        encountered_sources["doctor_hygiene"].add("workflow_alignment")
    if workflow_alignment["readiness_included"]:
        encountered_sources["adaptive_reviewer_confidence"].add("workflow_alignment")
        encountered_sources["governance_policy"].add("workflow_alignment")
    if scenario_runway_ratio < 1.0:
        encountered_sources["scalability_readiness"].add("scenario_capacity")
    else:
        encountered_sources["scalability_readiness"].add("scenario_capacity_ready")
    aspect_database = [
        {
            "aspect": aspect,
            "encountered": bool(encountered_sources[aspect]),
            "sources": sorted(encountered_sources[aspect]),
            "priority": (
                "now"
                if aspect in {"doctor_hygiene", "security_posture", "release_management"}
                else "next"
            ),
        }
        for aspect in canonical_aspects
    ]
    next_5_prompts_plan = [
        {
            "prompt_index": 1,
            "focus": "doctor baseline hardening",
            "goal": "Stabilize doctor lane and remove high-severity hygiene blockers.",
            "recommended_command": "python -m sdetkit doctor --repo --ci --deps --upgrade-audit --format json",
            "final_prompt": (
                "Run the doctor hardening pass now. Analyze all failed checks, rank blockers by risk, "
                "and produce a step-by-step fix list with exact commands and expected outputs."
            ),
        },
        {
            "prompt_index": 2,
            "focus": "adaptive reviewer evidence refresh",
            "goal": "Re-run adaptive review and inspect contradiction clusters/probe confidence.",
            "recommended_command": "python -m sdetkit review . --format json",
            "final_prompt": (
                "Re-run adaptive review and explain contradictions. Tell me which signals conflict, "
                "what evidence is missing, and which probe should run next to increase confidence."
            ),
        },
        {
            "prompt_index": 3,
            "focus": "readiness depth and scenario runway",
            "goal": "Close readiness misses and expand automated scenario capacity toward target.",
            "recommended_command": "python -m sdetkit readiness . --format json",
            "final_prompt": (
                "Use readiness output to build an execution backlog: top 5 actions, owners, ETA, "
                "and measurable completion criteria to close production gaps."
            ),
        },
        {
            "prompt_index": 4,
            "focus": "gate confidence rehearsal",
            "goal": "Rehearse ship/no-ship evidence through canonical gate fast/release outputs.",
            "recommended_command": "python -m sdetkit gate fast --format json --stable-json && python -m sdetkit gate release --format json",
            "final_prompt": (
                "Run gate fast and gate release and summarize go/no-go. Highlight failing steps, "
                "root causes, and the shortest path to a passing release contract."
            ),
        },
        {
            "prompt_index": 5,
            "focus": "release-room final review",
            "goal": "Produce operator summary and confirm final gate decision with updated adaptive DB.",
            "recommended_command": "python -m sdetkit review . --format operator-json",
            "final_prompt": (
                "Prepare the final release-room decision brief from operator-json: gate decision, "
                "blockers, risk band, next 24h actions, and owner routing."
            ),
        },
    ]
    gate_fast_artifact_present = bool(artifact_index.get("gate_fast_json"))
    gate_release_artifact_present = bool(artifact_index.get("gate_release_json"))
    step_statuses = {
        1: "done" if workflow_alignment["doctor_included"] else "pending",
        2: "done",
        3: "done" if workflow_alignment["readiness_included"] else "pending",
        4: "done" if gate_fast_artifact_present and gate_release_artifact_present else "pending",
        5: "in_progress",
    }
    for step in next_5_prompts_plan:
        prompt_index = int(step.get("prompt_index", 0))
        step["implementation_status"] = step_statuses.get(prompt_index, "pending")
    implementation_summary = {
        "completed_steps": sum(
            1 for step in next_5_prompts_plan if step["implementation_status"] == "done"
        ),
        "in_progress_steps": sum(
            1 for step in next_5_prompts_plan if step["implementation_status"] == "in_progress"
        ),
        "pending_steps": sum(
            1 for step in next_5_prompts_plan if step["implementation_status"] == "pending"
        ),
        "total_steps": len(next_5_prompts_plan),
    }
    next_step = next(
        (
            {
                "prompt_index": int(step.get("prompt_index", 0)),
                "focus": str(step.get("focus", "")),
                "recommended_command": str(step.get("recommended_command", "")),
                "final_prompt": str(step.get("final_prompt", "")),
                "status": str(step.get("implementation_status", "pending")),
            }
            for step in next_5_prompts_plan
            if str(step.get("implementation_status")) in {"in_progress", "pending"}
        ),
        {
            "prompt_index": 0,
            "focus": "all_done",
            "recommended_command": "",
            "final_prompt": "All boost-plan prompts are completed.",
            "status": "done",
        },
    )
    autostart_lane = [
        str(step.get("recommended_command", ""))
        for step in next_5_prompts_plan
        if str(step.get("implementation_status")) in {"in_progress", "pending"}
    ]

    payload["adaptive_database"] = {
        "schema_version": "sdetkit.review.adaptive-database.v1",
        "scope": review_scope,
        "five_heads_overview": payload["five_heads"].get("overall", {}),
        "top5_actions": top5_actions,
        "aspect_database": {
            "catalog": aspect_database,
            "encountered_total": sum(1 for row in aspect_database if row["encountered"]),
            "total_aspects": len(aspect_database),
        },
        "execution_boost_plan": {
            "next_5_prompts_plan": next_5_prompts_plan,
            "copy_ready_prompts": [
                str(step.get("final_prompt", "")) for step in next_5_prompts_plan
            ],
            "implementation_summary": implementation_summary,
            "next_step": next_step,
            "autostart_lane": autostart_lane,
        },
        "workflow_alignment": workflow_alignment,
        "doctor_gate_contract": doctor_gate_contract,
        "readiness_snapshot": {
            "score": next(
                (
                    float(row.get("value", 0.0))
                    for row in supporting
                    if isinstance(row, dict) and str(row.get("kind")) == "readiness_score"
                ),
                0.0,
            ),
            "tier": next(
                (
                    str(row.get("value", "needs-work"))
                    for row in supporting
                    if isinstance(row, dict) and str(row.get("kind")) == "readiness_tier"
                ),
                "needs-work",
            ),
            "operational_tier": next(
                (
                    str(row.get("value", "needs-work"))
                    for row in supporting
                    if isinstance(row, dict)
                    and str(row.get("kind")) == "readiness_operational_tier"
                ),
                "needs-work",
            ),
            "top_tier_ready": next(
                (
                    bool(row.get("value", False))
                    for row in supporting
                    if isinstance(row, dict) and str(row.get("kind")) == "readiness_top_tier_ready"
                ),
                False,
            ),
            "check_scorecard": next(
                (
                    dict(row.get("value", {}))
                    for row in supporting
                    if isinstance(row, dict) and str(row.get("kind")) == "readiness_check_scorecard"
                ),
                {"total_checks": 0, "passed_checks": 0, "missed_checks": 0, "pass_rate": 0.0},
            ),
            "failed_checks": next(
                (
                    list(row.get("value", []))
                    for row in supporting
                    if isinstance(row, dict) and str(row.get("kind")) == "readiness_failed_checks"
                ),
                [],
            ),
            "scenario_capacity": next(
                (
                    dict(row.get("value", {}))
                    for row in supporting
                    if isinstance(row, dict)
                    and str(row.get("kind")) == "readiness_scenario_capacity"
                ),
                {
                    "target_scenarios": 250,
                    "detected_scenarios": 0,
                    "gap": 250,
                    "status": "needs-expansion",
                },
            ),
            "artifact": artifact_index.get("readiness_json"),
        },
        "adaptive_alignment": {
            "engine": "five_heads",
            "doctor_included": workflow_alignment["doctor_included"],
            "readiness_included": workflow_alignment["readiness_included"],
            "scenario_target": 250,
            "scenario_status": next(
                (
                    str(row.get("value", {}).get("status", "needs-expansion"))
                    for row in supporting
                    if isinstance(row, dict)
                    and str(row.get("kind")) == "readiness_scenario_capacity"
                ),
                "needs-expansion",
            ),
        },
        "quality_matrix": {
            "workflow_status": str(payload.get("status", "unknown")),
            "workflow_severity": str(payload.get("severity", "unknown")),
            "confidence_score": float(payload.get("confidence", {}).get("score", 0.0)),
            "findings_total": len(payload.get("findings", [])),
            "conflicts_total": len(payload.get("conflicting_signals", [])),
            "healthy_controls_total": len(payload.get("healthy_controls", [])),
            "findings_by_severity": findings_severity_counts,
        },
        "findings_analytics": {
            "by_severity": findings_severity_counts,
            "by_kind": findings_kind_counts,
            "high_priority_total": len(
                [
                    row
                    for row in payload.get("findings", [])
                    if isinstance(row, dict) and int(row.get("priority", 0)) >= 70
                ]
            ),
        },
        "action_analytics": {
            "tiers": action_tier_counts,
            "top_priorities": [
                int(item.get("priority", 0))
                for item in payload.get("prioritized_actions", [])
                if isinstance(item, dict)
            ][:10],
        },
        "scalability_posture": {
            "scenario_capacity": readiness_scenario_snapshot,
            "target_scenarios": target_scenarios,
            "detected_scenarios": detected_scenarios,
            "runway_ratio": scenario_runway_ratio,
            "scale_mode": "top-tier-ready"
            if scenario_runway_ratio >= 1.0
            else "expansion-required",
        },
        "release_readiness_contract": {
            "contract_id": contract_id,
            "generated_at_utc": generated_at_utc,
            "next_review_due_at_utc": next_review_due_utc,
            "ready_now": release_ready_now,
            "gate_decision": "ship" if release_ready_now else "hold",
            "blockers": release_blockers,
            "blocker_catalog": blocker_catalog,
            "owner_summary": owner_summary,
            "recommendation_engine": recommendation_engine,
            "recommendation_backlog": recommendation_backlog,
            "agent_orchestration": agent_orchestration,
            "trend": release_trend,
            "risk_score": release_risk_score,
            "risk_band": release_risk_band,
            "sla_review_hours": sla_review_hours,
            "next_24h_actions": next_24h_actions,
            "next_72h_actions": next_72h_actions,
            "recommended_sequence": [
                "python -m sdetkit doctor --format json",
                "python -m sdetkit readiness . --format json",
                "python -m sdetkit gate fast --format json --stable-json",
                "python -m sdetkit gate release --format json",
                "python -m sdetkit review . --format operator-json",
            ],
        },
        "probe_memory_updates": payload["adaptive_review"]["probe_memory"].get("updates", []),
    }
    ai_assistant = payload["adaptive_review"].get("ai_assistant", {})
    if isinstance(ai_assistant, dict):
        ai_assistant["workflow_alignment"] = workflow_alignment
        ai_assistant["top5_actions"] = top5_actions
        ai_assistant["reviewer_engine_contract"] = {
            "five_heads_required": True,
            "top5_actions_required": True,
        }
        ai_assistant["doctor_gate_contract"] = doctor_gate_contract
        payload["adaptive_review"]["ai_assistant"] = ai_assistant
    payload["review_contract_check"] = _build_review_contract_check(payload)
    payload["operator_summary"] = _build_operator_summary(payload)

    json_path = out_dir / "review.json"
    txt_path = out_dir / "review.txt"
    packet_json_path = out_dir / _profile_packet_filename(selected_profile.name)
    operator_json_path = out_dir / "review-operator-summary.json"
    review_plan_path = out_dir / "review-plan.json"
    review_tracks_path = out_dir / "review-tracks.json"
    adaptive_db_path = out_dir / "adaptive-database.json"
    review_contract_check_path = out_dir / "review-contract-check.json"
    release_readiness_json_path = out_dir / "release-readiness.json"
    release_readiness_md_path = out_dir / "release-readiness.md"
    recommendation_backlog_json_path = out_dir / "recommendation-backlog.json"
    artifact_index["profile_packet_json"] = packet_json_path.as_posix()
    artifact_index["operator_summary_json"] = operator_json_path.as_posix()
    artifact_index["review_plan_json"] = review_plan_path.as_posix()
    artifact_index["review_tracks_json"] = review_tracks_path.as_posix()
    artifact_index["adaptive_database_json"] = adaptive_db_path.as_posix()
    artifact_index["review_contract_check_json"] = review_contract_check_path.as_posix()
    artifact_index["release_readiness_json"] = release_readiness_json_path.as_posix()
    artifact_index["release_readiness_md"] = release_readiness_md_path.as_posix()
    artifact_index["recommendation_backlog_json"] = recommendation_backlog_json_path.as_posix()
    payload["artifact_index"] = artifact_index
    payload["operator_summary"]["artifacts"] = artifact_index
    packet_json_path.write_text(
        json.dumps(profile_packet, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    operator_json_path.write_text(
        json.dumps(payload["operator_summary"], sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    review_plan_path.write_text(
        json.dumps(adaptive_plan, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    review_tracks_path.write_text(
        json.dumps({"tracks": likely_tracks}, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    adaptive_db_path.write_text(
        json.dumps(payload["adaptive_database"], sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    review_contract_check_path.write_text(
        json.dumps(payload["review_contract_check"], sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    release_readiness_json_path.write_text(
        json.dumps(
            payload["adaptive_database"]["release_readiness_contract"], sort_keys=True, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    release_readiness_md_path.write_text(
        _render_release_readiness_markdown(
            payload["adaptive_database"]["release_readiness_contract"]
        ),
        encoding="utf-8",
    )
    recommendation_backlog_json_path.write_text(
        json.dumps(
            payload["adaptive_database"]["release_readiness_contract"].get(
                "recommendation_backlog", []
            ),
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    txt_path.write_text(_render_text(payload), encoding="utf-8")

    if not no_workspace:
        payload["adaptive_review"]["probe_memory"]["workspace_artifact"] = _write_probe_memory(
            workspace_root=workspace_root,
            scope=review_scope,
            memory=updated_probe_memory,
        )

    if not no_workspace:
        workspace_entry = record_workspace_run(
            workspace_root=workspace_root,
            workflow="review",
            scope=review_scope,
            payload=payload,
            artifacts={"review_json": json_path.as_posix(), "review_text": txt_path.as_posix()},
            recommendations=[
                str(item.get("action", ""))
                for item in payload.get("prioritized_actions", [])
                if isinstance(item, dict)
            ],
        )
        payload["workspace"] = workspace_entry
        json_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    rc = EXIT_OK if payload["status"] == "pass" else EXIT_FINDINGS
    return rc, payload, json_path, txt_path


def _render_text(payload: dict[str, Any]) -> str:
    operator = payload.get("operator_summary", {})
    if not isinstance(operator, dict):
        operator = {}
    profile = payload.get("profile", {})
    profile_name = str(profile.get("name", "release")) if isinstance(profile, dict) else "release"
    max_matters = 5
    if isinstance(profile, dict):
        max_matters = int(
            REVIEW_PROFILES.get(
                str(profile.get("name", "")), REVIEW_PROFILES["release"]
            ).max_text_matters
        )
    lines: list[str] = [
        f"SDETKit review: {payload['review_status']}",
        f"profile: {profile_name} style: {profile.get('summary_style', 'release-gate')}",
        f"path: {payload['path']}",
        f"status: {payload['status']} severity: {payload['severity']}",
        f"confidence: {payload.get('confidence', {}).get('score')}",
    ]
    request_context = payload.get("request_context", {})
    if isinstance(request_context, dict) and request_context.get("work_id"):
        lines.append(f"work_id: {request_context.get('work_id')}")
    if profile_name == "release":
        lines.append("release_gate_decision:")
        lines.append(f"- decision: {payload.get('profile_packet', {}).get('decision', 'watch')}")
        lines.append("blockers:")
    elif profile_name == "triage":
        lines.append("incident_board:")
        lines.append("top_incidents:")
    elif profile_name == "forensics":
        lines.append("evidence_ledger:")
        lines.append("findings:")
    else:
        lines.append("trend_watch:")
        lines.append("active_signals:")

    for item in payload.get("top_matters", [])[:max_matters]:
        if not isinstance(item, dict):
            continue
        lines.append(f"- [{item.get('priority', 0)}] {item.get('kind')}: {item.get('message')}")
    snapshot = operator.get("situation", {})
    if isinstance(snapshot, dict):
        lines.append("operator_snapshot:")
        lines.append(f"- findings: {snapshot.get('findings_count', 0)}")
        lines.append(f"- contradictions: {snapshot.get('contradictions_count', 0)}")
        lines.append(f"- likely_tracks: {snapshot.get('likely_tracks_count', 0)}")
        lines.append(f"- probes_executed: {snapshot.get('executed_probes_count', 0)}")
    five_heads = payload.get("five_heads", {})
    if isinstance(five_heads, dict):
        heads = five_heads.get("heads", {})
        if isinstance(heads, dict) and heads:
            lines.append("five_heads:")
            for head_name in sorted(heads):
                head = heads.get(head_name, {})
                if not isinstance(head, dict):
                    continue
                lines.append(
                    f"- {head_name}: score={head.get('score')} status={head.get('status')} signal={head.get('signal')}"
                )
    changed = operator.get("changed_since_previous", [])
    if isinstance(changed, list) and changed:
        lines.append("what_changed:")
        for row in changed[:3]:
            if not isinstance(row, dict):
                continue
            lines.append(f"- {row.get('kind')}: {row.get('message')}")
    why = operator.get("judgment_rationale", [])
    if isinstance(why, list) and why:
        lines.append("why_this_judgment:")
        for row in why[:4]:
            lines.append(f"- {row}")
    if profile_name == "triage":
        lines.append("next_actions_now:")
    elif profile_name == "monitor":
        lines.append("watch_actions_now:")
    else:
        lines.append("what_to_do_now:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "now":
            lines.append(f"- {action.get('action')}")
    if profile_name == "forensics":
        lines.append("analysis_queue_next:")
    else:
        lines.append("what_to_do_next:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "next":
            lines.append(f"- {action.get('action')}")
    if profile_name == "monitor":
        lines.append("watchlist:")
    else:
        lines.append("what_to_monitor:")
    for action in payload.get("prioritized_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("tier")) == "monitor":
            lines.append(f"- {action.get('action')}")
    if payload.get("conflicting_evidence"):
        lines.append(f"conflicts: {len(payload['conflicting_evidence'])}")
    graph = payload.get("contradiction_graph", {})
    if isinstance(graph, dict):
        clusters = graph.get("clusters", [])
        if isinstance(clusters, list) and clusters:
            lines.append(f"contradiction_clusters: {len(clusters)}")
    adaptive = payload.get("adaptive_review", {})
    if isinstance(adaptive, dict):
        escalation = adaptive.get("escalation", {})
        stop = adaptive.get("stop_decision", {})
        lines.append("adaptive_review:")
        lines.append(f"- escalation_needed: {escalation.get('needed')}")
        for reason in escalation.get("reasons", [])[:3]:
            lines.append(f"  - reason: {reason}")
        lines.append(
            f"- probes_executed: {len([p for p in adaptive.get('executed_probes', []) if p.get('status') == 'executed'])}"
        )
        lines.append(f"- stop: {stop.get('stop')}")
        lines.append(f"- stop_reason: {stop.get('reason')}")
    tracks = payload.get("likely_issue_tracks", [])
    if isinstance(tracks, list) and tracks:
        lines.append("likely_issue_tracks:")
        for track in tracks[:3]:
            if not isinstance(track, dict):
                continue
            lines.append(
                f"- [{track.get('priority', 0)}] {track.get('track')}: likelihood={track.get('likelihood')}"
            )
    lines.append("")
    return "\n".join(lines)


def _render_release_readiness_markdown(contract: dict[str, Any]) -> str:
    contract_id = str(contract.get("contract_id", "unknown"))
    decision = str(contract.get("gate_decision", "hold")).strip().lower()
    ready_now = bool(contract.get("ready_now", False))
    generated_at = str(contract.get("generated_at_utc", ""))
    next_due_at = str(contract.get("next_review_due_at_utc", ""))
    risk_score = int(contract.get("risk_score", 0))
    risk_band = str(contract.get("risk_band", "low"))
    sla_hours = int(contract.get("sla_review_hours", 72))
    blockers = [str(item) for item in contract.get("blockers", [])]
    blocker_catalog = contract.get("blocker_catalog", [])
    if not isinstance(blocker_catalog, list):
        blocker_catalog = []
    owner_summary = contract.get("owner_summary", [])
    if not isinstance(owner_summary, list):
        owner_summary = []
    recommendation_engine = contract.get("recommendation_engine", {})
    if not isinstance(recommendation_engine, dict):
        recommendation_engine = {}
    recommendation_backlog = contract.get("recommendation_backlog", [])
    if not isinstance(recommendation_backlog, list):
        recommendation_backlog = []
    agent_orchestration = contract.get("agent_orchestration", [])
    if not isinstance(agent_orchestration, list):
        agent_orchestration = []
    trend = contract.get("trend", {})
    if not isinstance(trend, dict):
        trend = {}
    actions_24h = [str(item) for item in contract.get("next_24h_actions", [])]
    actions_72h = [str(item) for item in contract.get("next_72h_actions", [])]
    sequence = [str(item) for item in contract.get("recommended_sequence", [])]

    lines = [
        "# Release Readiness Contract",
        "",
        f"- Contract ID: `{contract_id}`",
        f"- Gate decision: **{decision}**",
        f"- Ready now: **{str(ready_now).lower()}**",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Next review due (UTC): `{next_due_at}`",
        f"- Risk: **{risk_band}** (`score={risk_score}`)",
        f"- SLA review window: **{sla_hours}h**",
        f"- Blockers: **{len(blockers)}**",
        (
            "- Trend: "
            f"prev_decision=`{trend.get('previous_gate_decision', 'unknown')}`, "
            f"decision_changed={trend.get('decision_changed', False)}, "
            f"blockers_delta={trend.get('blockers_delta', 0)}"
        ),
        "",
        "## Blockers",
    ]
    if blockers:
        lines.extend([f"- {item}" for item in blockers])
    else:
        lines.append("- none")
    if blocker_catalog:
        lines.extend(["", "## Blocker details"])
        for row in blocker_catalog[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- "
                f"{row.get('id')} "
                f"(kind={row.get('kind')}, severity={row.get('severity')}, priority={row.get('priority')}, "
                f"owner={row.get('owner_team')}, sla={row.get('response_sla_hours')}h)"
            )
            lines.append(f"  - why: {row.get('why_it_matters', '')}")
            lines.append(f"  - next: {row.get('next_action', '')}")
    if owner_summary:
        lines.extend(["", "## Owner summary"])
        for row in owner_summary:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- "
                f"{row.get('owner_team')}: blockers={row.get('blocker_count')}, "
                f"max_priority={row.get('max_priority')}, "
                f"min_sla_hours={row.get('min_response_sla_hours')}"
            )
    rec_now = recommendation_engine.get("now", [])
    rec_next = recommendation_engine.get("next_72h", [])
    rec_watch = recommendation_engine.get("watchlist", [])
    owner_routes = recommendation_engine.get("owner_routes", [])
    if not isinstance(rec_now, list):
        rec_now = []
    if not isinstance(rec_next, list):
        rec_next = []
    if not isinstance(rec_watch, list):
        rec_watch = []
    if not isinstance(owner_routes, list):
        owner_routes = []
    lines.extend(["", "## Recommendation engine"])
    lines.append("### Now")
    lines.extend([f"- {item}" for item in rec_now[:5]] or ["- none"])
    lines.append("")
    lines.append("### Next 72h")
    lines.extend([f"- {item}" for item in rec_next[:8]] or ["- none"])
    lines.append("")
    lines.append("### Watchlist")
    lines.extend([f"- {item}" for item in rec_watch[:8]] or ["- none"])
    if owner_routes:
        lines.extend(["", "### Owner routes"])
        for row in owner_routes[:6]:
            if not isinstance(row, dict):
                continue
            lines.append(f"- {row.get('owner_team')}: focus={row.get('priority_focus')}")
            for action in row.get("recommended_actions", [])[:3]:
                lines.append(f"  - {action}")
    if recommendation_backlog:
        lines.extend(["", "### Backlog ranking"])
        for row in recommendation_backlog[:10]:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- "
                f"{row.get('action')} "
                f"(lane={row.get('lane')}, owner={row.get('owner_team')}, "
                f"priority_index={row.get('priority_index')})"
            )
    if agent_orchestration:
        lines.extend(["", "## Agent playbook"])
        for row in agent_orchestration:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('agent_id')}: {row.get('purpose')} (when: {row.get('when_to_use')})"
            )
            for cmd in row.get("suggested_commands", [])[:3]:
                lines.append(f"  - {cmd}")
    lines.extend(["", "## Next 24h actions"])
    if actions_24h:
        lines.extend([f"- {item}" for item in actions_24h])
    else:
        lines.append("- none")
    lines.extend(["", "## Next 72h actions"])
    if actions_72h:
        lines.extend([f"- {item}" for item in actions_72h])
    else:
        lines.append("- none")
    lines.extend(["", "## Recommended execution sequence"])
    lines.extend([f"{idx + 1}. {item}" for idx, item in enumerate(sequence)])
    lines.append("")
    return "\n".join(lines)


def _build_operator_summary(payload: dict[str, Any]) -> dict[str, Any]:
    tracks = [row for row in payload.get("likely_issue_tracks", []) if isinstance(row, dict)]
    conflicts = [row for row in payload.get("conflicting_evidence", []) if isinstance(row, dict)]
    findings = [row for row in payload.get("top_matters", []) if isinstance(row, dict)]
    adaptive = payload.get("adaptive_review", {})
    executed_probes = []
    if isinstance(adaptive, dict):
        executed_probes = [
            row
            for row in adaptive.get("executed_probes", [])
            if isinstance(row, dict) and row.get("status") == "executed"
        ]
    thresholds = payload.get("judgment", {}).get("profile_thresholds", {})
    if not isinstance(thresholds, dict):
        thresholds = {}
    effective_priority = thresholds.get("effective_max_priority", 0)
    rationale: list[str] = []
    rationale.append(
        f"Status is '{payload.get('status')}' because effective priority reached "
        f"{effective_priority} "
        f"and contradictions count is {len(conflicts)}."
    )
    confidence = payload.get("confidence", {})
    if isinstance(confidence, dict):
        rationale.append(
            f"Confidence is {confidence.get('score')} ({confidence.get('level', 'unknown')}) from available workflow evidence."
        )
    if tracks:
        top_track = tracks[0]
        rationale.append(
            f"Top likely issue track is '{top_track.get('track')}' with likelihood {top_track.get('likelihood')}."
        )
    if conflicts:
        rationale.append(
            f"{len(conflicts)} contradiction signal(s) require verification before full trust."
        )
    actions = [row for row in payload.get("prioritized_actions", []) if isinstance(row, dict)]
    request_context = payload.get("request_context", {})
    if not isinstance(request_context, dict):
        request_context = {}
    raw_work_context = request_context.get("work_context", {})
    if not isinstance(raw_work_context, dict):
        raw_work_context = {}
    adaptive_database = payload.get("adaptive_database", {})
    if isinstance(adaptive_database, dict):
        adaptive_database = dict(adaptive_database)
        release_contract = adaptive_database.get("release_readiness_contract", {})
        if isinstance(release_contract, dict):
            release_contract = dict(release_contract)
            release_contract.pop("generated_at_utc", None)
            release_contract.pop("next_review_due_at_utc", None)
            adaptive_database["release_readiness_contract"] = release_contract

    return {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "situation": {
            "status": payload.get("status"),
            "severity": payload.get("severity"),
            "confidence_score": payload.get("confidence", {}).get("score"),
            "findings_count": len(findings),
            "contradictions_count": len(conflicts),
            "likely_tracks_count": len(tracks),
            "executed_probes_count": len(executed_probes),
        },
        "judgment_rationale": rationale,
        "changed_since_previous": [
            row for row in payload.get("changed_since_previous", []) if isinstance(row, dict)
        ][:5],
        "actions": {
            "now": [row for row in actions if row.get("tier") == "now"][:5],
            "next": [row for row in actions if row.get("tier") == "next"][:5],
            "monitor": [row for row in actions if row.get("tier") == "monitor"][:5],
        },
        "contradictions": conflicts[:5],
        "tracks": tracks[:5],
        "probes": executed_probes[:5],
        "five_heads": payload.get("five_heads", {}),
        "request_context": {
            "work_id": str(request_context.get("work_id", "")).strip(),
            "work_context": {str(k): str(v) for k, v in raw_work_context.items() if str(k).strip()},
        },
        "code_scanning": payload.get("code_scanning", {}),
        "adaptive_database": adaptive_database,
        "review_contract_check": payload.get("review_contract_check", {}),
        "doctor_gate_contract": payload.get("doctor_gate_contract", {}),
        "artifacts": payload.get("artifact_index", {}),
    }


def _build_review_contract_check(payload: dict[str, Any]) -> dict[str, Any]:
    release_contract = payload.get("adaptive_database", {}).get("release_readiness_contract", {})
    if not isinstance(release_contract, dict):
        release_contract = {}
    recommendation_backlog = release_contract.get("recommendation_backlog", [])
    if not isinstance(recommendation_backlog, list):
        recommendation_backlog = []
    blocker_catalog = release_contract.get("blocker_catalog", [])
    if not isinstance(blocker_catalog, list):
        blocker_catalog = []
    owner_summary = release_contract.get("owner_summary", [])
    if not isinstance(owner_summary, list):
        owner_summary = []
    agent_orchestration = release_contract.get("agent_orchestration", [])
    if not isinstance(agent_orchestration, list):
        agent_orchestration = []

    gate_decision = str(release_contract.get("gate_decision", "hold"))
    blockers = [str(item) for item in release_contract.get("blockers", [])]
    issues: list[str] = []

    if gate_decision == "ship" and blockers:
        issues.append("gate_decision is ship but blockers are still present")
    if gate_decision == "hold" and not blockers:
        issues.append("gate_decision is hold but blockers list is empty")
    if blockers and not blocker_catalog:
        issues.append("blockers present but blocker_catalog is empty")
    if blocker_catalog and not owner_summary:
        issues.append("blocker_catalog present but owner_summary is empty")
    if recommendation_backlog and not agent_orchestration:
        issues.append("recommendation_backlog present but agent_orchestration is empty")

    return {
        "schema_version": "sdetkit.review.contract-check.v1",
        "status": "pass" if not issues else "fail",
        "checks": {
            "gate_matches_blockers": not (gate_decision == "ship" and blockers)
            and not (gate_decision == "hold" and not blockers),
            "blocker_catalog_present_when_blocked": not blockers or bool(blocker_catalog),
            "owner_summary_present_when_catalog_exists": not blocker_catalog or bool(owner_summary),
            "agent_orchestration_present_when_backlog_exists": not recommendation_backlog
            or bool(agent_orchestration),
        },
        "issues": issues,
        "signals": {
            "gate_decision": gate_decision,
            "blockers_count": len(blockers),
            "blocker_catalog_count": len(blocker_catalog),
            "owner_summary_count": len(owner_summary),
            "recommendation_backlog_count": len(recommendation_backlog),
            "agent_orchestration_count": len(agent_orchestration),
        },
    }


def _build_five_head_engine(payload: dict[str, Any]) -> dict[str, Any]:
    findings = [row for row in payload.get("top_matters", []) if isinstance(row, dict)]
    conflicts = [row for row in payload.get("conflicting_evidence", []) if isinstance(row, dict)]
    controls = [str(row) for row in payload.get("healthy_controls", [])]
    tracks = [row for row in payload.get("likely_issue_tracks", []) if isinstance(row, dict)]

    def _score(base: int, penalty: int) -> int:
        return max(0, min(100, base - penalty))

    doctor_hits = sum(1 for row in findings if str(row.get("kind")) == "doctor")
    inspect_hits = sum(1 for row in findings if str(row.get("kind", "")).startswith("inspect"))
    high_priority = sum(1 for row in findings if int(row.get("priority", 0)) >= 60)
    contradiction_penalty = len(conflicts) * 9

    heads: dict[str, dict[str, Any]] = {
        "quality": {
            "score": _score(92, doctor_hits * 10 + high_priority * 4),
            "signal": "doctor+lint+test pressure",
        },
        "reliability": {
            "score": _score(90, inspect_hits * 8 + contradiction_penalty),
            "signal": "drift+stability contradictions",
        },
        "security": {
            "score": _score(88, contradiction_penalty + (0 if "security_files" in controls else 6)),
            "signal": "governance+policy controls",
        },
        "delivery": {
            "score": _score(90, high_priority * 8 + len(tracks) * 3),
            "signal": "priority queue heat",
        },
        "evidence": {
            "score": _score(94, len(conflicts) * 7 + (0 if controls else 10)),
            "signal": "supporting vs conflicting evidence",
        },
    }

    def _coerce_score(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        return 0

    for row in heads.values():
        score = _coerce_score(row.get("score"))
        row["status"] = "strong" if score >= 80 else ("watch" if score >= 60 else "critical")
    return {
        "schema_version": "sdetkit.review.five-heads.v1",
        "heads": heads,
        "overall": {
            "score": round(sum(_coerce_score(row.get("score")) for row in heads.values()) / 5.0, 1),
            "status": payload.get("status", "watch"),
        },
    }


def _run_interactive_review(payload: dict[str, Any]) -> None:
    operator = payload.get("operator_summary", {})
    if not isinstance(operator, dict):
        operator = {}
    sections = {
        "1": ("situation", operator.get("situation", {})),
        "2": ("why_this_judgment", operator.get("judgment_rationale", [])),
        "3": ("what_changed", operator.get("changed_since_previous", [])),
        "4": ("actions", operator.get("actions", {})),
        "5": ("likely_tracks", operator.get("tracks", [])),
        "6": ("contradictions", operator.get("contradictions", [])),
        "7": ("probes", operator.get("probes", [])),
        "8": ("artifacts", operator.get("artifacts", {})),
    }
    sys.stdout.write("SDETKit interactive review navigator\n")
    sys.stdout.write(
        "Choose section: [1] situation [2] why [3] changed [4] actions [5] tracks [6] contradictions [7] probes [8] artifacts [q] quit\n"
    )
    while True:
        sys.stdout.write("> ")
        sys.stdout.flush()
        choice = sys.stdin.readline()
        if choice is None:
            break
        value = choice.strip().lower()
        if value in {"q", "quit", "exit", ""}:
            break
        selected = sections.get(value)
        if not selected:
            sys.stdout.write("unknown option\n")
            continue
        name, body = selected
        sys.stdout.write(f"[{name}]\n")
        sys.stdout.write(json.dumps(body, sort_keys=True, indent=2) + "\n")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit review",
        description="Front-door SDETKit review workflow that orchestrates doctor/inspect/compare/project/history.",
    )
    p.add_argument("path", help="Repo/data/project/workspace path to review")
    p.add_argument("--workspace-root", default=".sdetkit/workspace", help="Shared workspace root")
    p.add_argument(
        "--out-dir", default=None, help="Output directory (default: .sdetkit/review/<path-slug>)"
    )
    p.add_argument(
        "--profile",
        default="release",
        choices=sorted(REVIEW_PROFILES),
        help="Review operating profile: release, triage, forensics, monitor.",
    )
    p.add_argument(
        "--format",
        choices=["text", "json", "operator-json"],
        default="text",
        help=(
            "Output format: text (operator narrative), json (full payload for deep/debug automation), "
            "or operator-json (stable operator-facing integration contract; preferred for CI/operator parsers)."
        ),
    )
    p.add_argument(
        "--interactive",
        action="store_true",
        help="Open an interactive operator navigator after review completes.",
    )
    p.add_argument(
        "--no-workspace", action="store_true", help="Disable workspace history recording"
    )
    p.add_argument(
        "--work-id",
        default="",
        help="Optional external work identifier (ticket/story/incident id) to stamp into review outputs.",
    )
    p.add_argument(
        "--work-context",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Optional context pair for AI/fix handoff metadata; repeat per key.",
    )
    p.add_argument(
        "--code-scan-json",
        default=None,
        help="Optional JSON/SARIF code scanning report to fold into adaptive review and AI guidance.",
    )
    return p


def _parse_work_context(entries: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in entries:
        raw = str(entry).strip()
        if not raw:
            continue
        key, sep, value = raw.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"review: invalid --work-context entry '{entry}' (expected KEY=VALUE)")
        out[key.strip()] = value.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    try:
        target = safe_path(Path.cwd(), ns.path, allow_absolute=True)
        out_dir = (
            safe_path(Path.cwd(), ns.out_dir, allow_absolute=True)
            if ns.out_dir
            else Path(".sdetkit") / "review" / _safe_slug(target.resolve().name)
        )
        workspace_root = safe_path(Path.cwd(), ns.workspace_root, allow_absolute=True)
    except SecurityError as exc:
        sys.stderr.write(f"review: path rejected: {exc}\n")
        return EXIT_FINDINGS
    try:
        work_context = _parse_work_context(list(ns.work_context))
        rc, payload, _, _ = run_review(
            target=target,
            out_dir=out_dir,
            workspace_root=workspace_root,
            profile=ns.profile,
            no_workspace=ns.no_workspace,
            work_id=str(ns.work_id or "").strip(),
            work_context=work_context,
            code_scan_json=Path(ns.code_scan_json) if ns.code_scan_json else None,
        )
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    if ns.format == "json":
        output = json.dumps(payload, sort_keys=True)
    elif ns.format == "operator-json":
        output = json.dumps(payload.get("operator_summary", {}), sort_keys=True)
    else:
        output = _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    if ns.interactive:
        _run_interactive_review(payload)
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
