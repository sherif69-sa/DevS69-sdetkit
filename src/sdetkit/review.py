from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import doctor, inspect_project
from .evidence_workspace import load_workspace_manifest, record_workspace_run
from .inspect_compare import run_compare
from .inspect_data import run_inspect
from .judgment import build_judgment, load_latest_previous_payload
from .review_engine import (
    apply_probe_memory_update,
    apply_probe_result_feedback,
    build_contradiction_graph,
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

SCHEMA_VERSION = "sdetkit.review.v2"
EXIT_OK = 0
EXIT_FINDINGS = 2


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
    findings = _sorted_findings([item for item in payload.get("top_matters", []) if isinstance(item, dict)])
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
                item for item in payload.get("supporting_evidence", []) if item.get("kind") == "workspace_runs"
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
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"review: expected JSON object at {path}")
    return loaded


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
        moved["skip_reason"] = str(row.get("skip_reason", "")) or "probe planned but not executed in deepen stage"
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


def _run_doctor(target: Path, out_dir: Path, workspace_root: Path, no_workspace: bool) -> tuple[int, dict[str, Any], Path]:
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
            rc = int(exc.code)
    payload = _load_json(doctor_json)
    return int(rc), payload, doctor_json


def _review_scope_for_target(target: Path) -> str:
    return _safe_slug(target.resolve().as_posix())


def run_review(
    *,
    target: Path,
    out_dir: Path,
    workspace_root: Path,
    profile: str = "release",
    no_workspace: bool = False,
) -> tuple[int, dict[str, Any], Path, Path]:
    target = target.resolve()
    if not target.exists():
        raise ValueError(f"review: path does not exist: {target}")

    detection = _detect_mode(target)
    selected_profile = _coerce_profile(profile)
    workflow_plan = _workflows_for_profile(detection, selected_profile)
    review_scope = _review_scope_for_target(target)
    out_dir.mkdir(parents=True, exist_ok=True)
    probe_memory = _load_probe_memory(workspace_root=workspace_root, scope=review_scope) if not no_workspace else {
        "schema_version": "sdetkit.review.probe-memory.v1",
        "probes": {},
    }

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
        supporting.append({"kind": "inspect_files", "value": inspect_payload.get("summary", {}).get("files_analyzed", 0)})
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
                *( ["--no-workspace"] if no_workspace else []),
            ]
        )
        payload = _load_json(project_out / "inspect-project.json")
        artifact_index["inspect_project_json"] = (project_out / "inspect-project.json").as_posix()
        artifact_index["inspect_project_txt"] = (project_out / "inspect-project.txt").as_posix()
        project_status = "ok" if rc == 0 else "findings"
        source_workflows.append({"workflow": "inspect-project", "status": project_status})
        baseline_stage["checks_run"].append({"check": "inspect-project", "status": project_status})
        supporting.append({"kind": "inspect_project_scopes", "value": payload.get("summary", {}).get("scopes", 0)})
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

    if inspect_payload and "inspect-compare" in deepen_checks and escalation.needed and not no_workspace:
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

    weighted_findings = [{**item, "priority": profile_weighted_priority(item, selected_profile)} for item in findings]
    weighted_conflicts = [
        {
            **item,
            "priority": selected_profile.contradiction_weight,
        }
        for item in conflicting
    ]
    contradiction_count = len(conflicting)
    contradiction_boost = contradiction_count * selected_profile.contradiction_weight
    effective_max_priority = max([0, *(int(item.get("priority", 0)) for item in weighted_findings)]) + contradiction_boost
    completeness = min(1.0, max(0.2, len(source_workflows) / 5.0))
    stability = 0.7 if conflicting else 0.85
    workflow_ok = len(weighted_findings) == 0
    blocking = effective_max_priority >= selected_profile.fail_threshold or contradiction_count >= selected_profile.contradiction_fail_count

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
    if effective_max_priority >= selected_profile.fail_threshold or contradiction_count >= selected_profile.contradiction_fail_count:
        profile_status = "fail"
    elif effective_max_priority >= selected_profile.watch_threshold or contradiction_count >= selected_profile.contradiction_watch_count:
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
    confidence["level"] = profile_confidence_level(float(confidence.get("score", 0.0)), selected_profile)
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
    previous_review = None
    previous_hash = None
    if not no_workspace:
        previous_review, previous_hash = load_latest_previous_payload(
            workspace_root=workspace_root,
            workflow="review",
            scope=review_scope,
        )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit",
        "workflow": "review",
        "profile": {
            "name": selected_profile.name,
            "summary_style": selected_profile.summary_style,
            "orchestration_depth": "deep" if selected_profile.name in {"release", "forensics"} else "focused",
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
    }
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
        executed_probes=[row for row in adaptive_plan.get("executed_probes", []) if row.get("status") == "executed"],
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
        executed_probes=[row for row in adaptive_plan.get("executed_probes", []) if isinstance(row, dict)],
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
        executed_probes=[row for row in adaptive_plan.get("executed_probes", []) if isinstance(row, dict)],
        conflicts=weighted_conflicts,
        findings=weighted_findings,
        tracks=payload["likely_issue_tracks"],
    )
    final_confidence = investigation_confidence(
        source_workflows=source_workflows,
        findings=weighted_findings,
        conflicts=weighted_conflicts,
    )
    final_confidence = round(max(0.0, min(1.0, final_confidence + float(probe_feedback.get("confidence_delta", 0.0)))), 2)
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

    json_path = out_dir / "review.json"
    txt_path = out_dir / "review.txt"
    packet_json_path = out_dir / _profile_packet_filename(selected_profile.name)
    review_plan_path = out_dir / "review-plan.json"
    review_tracks_path = out_dir / "review-tracks.json"
    artifact_index["profile_packet_json"] = packet_json_path.as_posix()
    artifact_index["review_plan_json"] = review_plan_path.as_posix()
    artifact_index["review_tracks_json"] = review_tracks_path.as_posix()
    payload["artifact_index"] = artifact_index
    packet_json_path.write_text(json.dumps(profile_packet, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    review_plan_path.write_text(json.dumps(adaptive_plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    review_tracks_path.write_text(json.dumps({"tracks": likely_tracks}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
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
            recommendations=[str(item.get("action", "")) for item in payload.get("prioritized_actions", []) if isinstance(item, dict)],
        )
        payload["workspace"] = workspace_entry
        json_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    rc = EXIT_OK if payload["status"] == "pass" else EXIT_FINDINGS
    return rc, payload, json_path, txt_path


def _render_text(payload: dict[str, Any]) -> str:
    profile = payload.get("profile", {})
    profile_name = str(profile.get("name", "release")) if isinstance(profile, dict) else "release"
    max_matters = 5
    if isinstance(profile, dict):
        max_matters = int(REVIEW_PROFILES.get(str(profile.get("name", "")), REVIEW_PROFILES["release"]).max_text_matters)
    lines: list[str] = [
        f"SDETKit review: {payload['review_status']}",
        f"profile: {profile_name} style: {profile.get('summary_style', 'release-gate')}",
        f"path: {payload['path']}",
        f"status: {payload['status']} severity: {payload['severity']}",
        f"confidence: {payload.get('confidence', {}).get('score')}",
    ]
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
        lines.append(f"- probes_executed: {len([p for p in adaptive.get('executed_probes', []) if p.get('status') == 'executed'])}")
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


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit review",
        description="Front-door SDETKit review workflow that orchestrates doctor/inspect/compare/project/history.",
    )
    p.add_argument("path", help="Repo/data/project/workspace path to review")
    p.add_argument("--workspace-root", default=".sdetkit/workspace", help="Shared workspace root")
    p.add_argument("--out-dir", default=None, help="Output directory (default: .sdetkit/review/<path-slug>)")
    p.add_argument(
        "--profile",
        default="release",
        choices=sorted(REVIEW_PROFILES),
        help="Review operating profile: release, triage, forensics, monitor.",
    )
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--no-workspace", action="store_true", help="Disable workspace history recording")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    target = Path(ns.path)
    out_dir = Path(ns.out_dir) if ns.out_dir else Path(".sdetkit") / "review" / _safe_slug(target.resolve().name)
    try:
        rc, payload, _, _ = run_review(
            target=target,
            out_dir=out_dir,
            workspace_root=Path(ns.workspace_root),
            profile=ns.profile,
            no_workspace=ns.no_workspace,
        )
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return EXIT_FINDINGS

    output = json.dumps(payload, sort_keys=True) if ns.format == "json" else _render_text(payload)
    sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
