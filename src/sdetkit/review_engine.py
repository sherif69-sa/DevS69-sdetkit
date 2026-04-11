from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdaptiveEscalationDecision:
    needed: bool
    reasons: tuple[str, ...]
    confidence_gate: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "needed": self.needed,
            "reasons": list(self.reasons),
            "confidence_gate": self.confidence_gate,
        }


@dataclass(frozen=True)
class AdaptiveStopDecision:
    stop: bool
    confidence_score: float
    confidence_threshold: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "stop": self.stop,
            "confidence_score": self.confidence_score,
            "confidence_threshold": self.confidence_threshold,
            "reason": self.reason,
        }


def profile_weighted_priority(item: dict[str, Any], profile: Any) -> int:
    base = int(item.get("priority", 0))
    kind = str(item.get("kind", "")).strip().lower()
    weight = 1.0
    if kind == "doctor":
        weight = float(profile.doctor_weight)
    elif kind == "inspect":
        weight = float(profile.inspect_weight)
    elif kind == "inspect-compare":
        weight = float(profile.compare_weight)
    elif kind == "inspect-project":
        weight = float(profile.inspect_project_weight)
    return max(0, min(100, int(round(base * weight))))


def profile_confidence_level(score: float, profile: Any) -> str:
    if score >= float(profile.confidence_high):
        return "high"
    if score >= float(profile.confidence_medium):
        return "medium"
    return "low"


def profile_priority_tier(priority: int, profile: Any) -> str:
    if priority >= int(profile.urgency_now_threshold):
        return "now"
    if priority >= int(profile.urgency_next_threshold):
        return "next"
    return "monitor"


def build_staged_plan(*, profile_name: str, stages: tuple[Any, ...], workflow_plan: dict[str, bool]) -> dict[str, Any]:
    stage_rows: list[dict[str, Any]] = []
    for stage in stages:
        checks = [name for name in stage.checks if workflow_plan.get(name.replace("-", "_"), False)]
        row: dict[str, Any] = {
            "name": stage.name,
            "intent": stage.intent,
            "checks_planned": checks,
            "checks_run": [],
        }
        if "deepen" in stage.name:
            row["ran"] = False
        stage_rows.append(row)
    return {
        "version": "sdetkit.review-plan.v1",
        "profile": profile_name,
        "stages": stage_rows,
        "escalation": {"needed": False, "reasons": [], "confidence_gate": None},
        "stop_decision": {},
    }


def investigation_confidence(
    *,
    source_workflows: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> float:
    coverage = min(1.0, max(0.25, len(source_workflows) / 4.0))
    evidence_consistency = 1.0 - min(0.75, len(conflicts) * 0.2)
    risk_pressure = min(0.7, len(findings) * 0.15)
    score = (coverage * 0.5) + (evidence_consistency * 0.35) + ((1.0 - risk_pressure) * 0.15)
    return round(max(0.0, min(1.0, score)), 2)


def decide_escalation(
    *,
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    baseline_confidence: float,
    confidence_threshold: float,
    force_deepen: bool,
) -> AdaptiveEscalationDecision:
    reasons: list[str] = []
    if findings:
        reasons.append("high-signal findings present in baseline layer")
    if conflicts:
        reasons.append("contradictory evidence requires disambiguation")
    if baseline_confidence < confidence_threshold:
        reasons.append(
            f"baseline confidence {baseline_confidence} below profile medium threshold {confidence_threshold}"
        )
    if force_deepen:
        reasons.append("forensics profile enforces deep evidence collection")
    return AdaptiveEscalationDecision(
        needed=bool(reasons),
        reasons=tuple(reasons),
        confidence_gate=baseline_confidence,
    )


def decide_stop(
    *,
    final_confidence: float,
    confidence_threshold: float,
    findings_count: int,
    conflicts_count: int,
) -> AdaptiveStopDecision:
    can_stop = final_confidence >= confidence_threshold and findings_count == 0 and conflicts_count == 0
    return AdaptiveStopDecision(
        stop=can_stop,
        confidence_score=final_confidence,
        confidence_threshold=confidence_threshold,
        reason=(
            "confidence sufficient and no unresolved contradictions"
            if can_stop
            else "continue investigation in next run or remediation cycle"
        ),
    )


def build_contradiction_graph(
    *,
    findings: list[dict[str, Any]],
    detection: dict[str, bool] | None = None,
    doctor_kind: str = "doctor",
    inspect_kind: str = "inspect",
) -> list[dict[str, Any]]:
    graph: list[dict[str, Any]] = []
    has_doctor_failure = any(str(f.get("kind", "")) == doctor_kind for f in findings)
    has_inspect_failure = any(str(f.get("kind", "")) == inspect_kind for f in findings)
    repo_like = bool((detection or {}).get("repo_like", False))
    if has_doctor_failure and not has_inspect_failure:
        graph.append(
            {
                "id": "review:conflict:repo-vs-data",
                "kind": "cross_surface_disagreement",
                "message": "Repo controls fail while local evidence diagnostics appear healthy.",
            }
        )
    if has_inspect_failure and not has_doctor_failure and repo_like:
        graph.append(
            {
                "id": "review:conflict:data-vs-repo",
                "kind": "cross_surface_disagreement",
                "message": "Repo controls pass while evidence diagnostics show anomalies.",
            }
        )
    return sorted(
        graph,
        key=lambda item: (str(item.get("kind", "")), str(item.get("id", "")), str(item.get("message", ""))),
    )


def build_contradiction_clusters(
    *,
    findings: list[dict[str, Any]],
    detection: dict[str, bool] | None = None,
) -> dict[str, Any]:
    flat = build_contradiction_graph(findings=findings, detection=detection)
    findings_by_kind: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        kind = str(item.get("kind", "unknown"))
        findings_by_kind.setdefault(kind, []).append(item)
    nodes: list[dict[str, Any]] = []
    for kind, items in sorted(findings_by_kind.items()):
        nodes.append(
            {
                "node_id": f"signal:{kind}",
                "kind": kind,
                "count": len(items),
                "max_priority": max(int(entry.get("priority", 0)) for entry in items),
            }
        )
    edges: list[dict[str, Any]] = []
    for item in flat:
        conflict_id = str(item.get("id", "conflict:unknown"))
        for node in nodes:
            edges.append(
                {
                    "edge_id": f"{conflict_id}->{node['node_id']}",
                    "relation": "conflicts_with",
                    "from": conflict_id,
                    "to": node["node_id"],
                    "weight": max(1, int(node.get("count", 1))),
                }
            )
    clusters: list[dict[str, Any]] = []
    if flat:
        clusters.append(
            {
                "cluster_id": "cluster:cross-surface",
                "kind": "cross_surface_disagreement",
                "importance": min(100, 35 + len(flat) * 20 + len(nodes) * 8),
                "contradictions": flat,
                "signals": [node["kind"] for node in nodes],
            }
        )
    elif len(nodes) >= 2:
        clusters.append(
            {
                "cluster_id": "cluster:multi-signal-tension",
                "kind": "multi_signal_tension",
                "importance": min(100, 30 + len(nodes) * 10),
                "contradictions": [],
                "signals": [node["kind"] for node in nodes],
            }
        )
    return {
        "version": "sdetkit.contradiction-graph.v1",
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "flat_contradictions": flat,
    }


def plan_adaptive_probes(
    *,
    detection: dict[str, bool],
    profile_name: str,
    findings: list[dict[str, Any]],
    contradiction_graph: dict[str, Any],
    has_previous_review: bool,
    changed: list[dict[str, Any]],
    max_probes: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    contradictory = len(contradiction_graph.get("flat_contradictions", []))
    cluster_pressure = len(contradiction_graph.get("clusters", []))
    finding_pressure = sum(max(0, int(item.get("priority", 0))) for item in findings)
    history_pressure = len([row for row in changed if str(row.get("kind")) in {"status", "severity"}])
    candidates = [
        {
            "probe_id": "probe:inspect-compare",
            "requires": "inspect_compare_available",
            "score": (35 if contradictory else 0)
            + (cluster_pressure * 12)
            + (finding_pressure // 6)
            + (15 if has_previous_review else 0),
            "reason": "Resolve whether recent evidence drift explains current contradictions/findings.",
        },
        {
            "probe_id": "probe:workspace-history",
            "requires": "workspace_like",
            "score": (20 if contradictory else 0) + (history_pressure * 20) + (10 if profile_name == "forensics" else 0),
            "reason": "Use repeated-run history to verify whether risk is persistent or newly introduced.",
        },
    ]
    executed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in sorted(candidates, key=lambda item: (-int(item["score"]), str(item["probe_id"]))):
        requires = str(row["requires"])
        enabled = bool(detection.get("workspace_like")) if requires == "workspace_like" else bool(
            detection.get("data_like")
        )
        should_run = enabled and int(row["score"]) >= 25 and len(executed) < max_probes
        target = executed if should_run else skipped
        target.append(
            {
                "probe_id": row["probe_id"],
                "score": int(row["score"]),
                "reason": row["reason"],
                "requires": requires,
                "status": "planned" if should_run else "skipped",
                "skip_reason": "" if should_run else ("probe preconditions missing or score below threshold"),
            }
        )
    return {"executed_probes": executed, "skipped_probes": skipped}


def apply_probe_result_feedback(
    *,
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    likely_tracks: list[dict[str, Any]],
    executed_probes: list[dict[str, Any]],
) -> dict[str, Any]:
    probe_pressure = len(executed_probes)
    confidence_delta = 0.08 if probe_pressure > 0 and not findings and not conflicts else -0.03 * probe_pressure
    status = "stable" if confidence_delta >= 0 else "risk-intensified"
    track_updates: list[dict[str, Any]] = []
    for track in likely_tracks[:3]:
        if not isinstance(track, dict):
            continue
        base = float(track.get("likelihood", 0.0))
        adjusted = round(max(0.0, min(0.99, base + (0.06 if confidence_delta < 0 else -0.04))), 2)
        track_updates.append(
            {
                "track_id": str(track.get("track_id", "")),
                "base_likelihood": base,
                "adjusted_likelihood": adjusted,
            }
        )
    return {
        "confidence_delta": round(confidence_delta, 2),
        "status": status,
        "track_updates": track_updates,
        "judgment_note": (
            "Probe outcomes reduced uncertainty in critical tracks."
            if confidence_delta >= 0
            else "Probe outcomes found additional pressure that increases risk confidence."
        ),
    }


def summarize_history_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(previous, dict):
        return [{"kind": "baseline", "message": "No previous review run found for this scope."}]
    changes: list[dict[str, Any]] = []
    prev_actions = previous.get("prioritized_actions", [])
    cur_actions = current.get("prioritized_actions", [])
    prev_now = len([a for a in prev_actions if isinstance(a, dict) and a.get("tier") == "now"])
    cur_now = len([a for a in cur_actions if isinstance(a, dict) and a.get("tier") == "now"])
    if prev_now != cur_now:
        changes.append({"kind": "action_pressure", "message": f"immediate_actions changed {prev_now} -> {cur_now}"})
    prev_status = str(previous.get("status", ""))
    cur_status = str(current.get("status", ""))
    if prev_status != cur_status:
        changes.append({"kind": "status", "message": f"status changed {prev_status} -> {cur_status}"})
    prev_sev = str(previous.get("severity", ""))
    cur_sev = str(current.get("severity", ""))
    if prev_sev != cur_sev:
        changes.append({"kind": "severity", "message": f"severity changed {prev_sev} -> {cur_sev}"})
    return changes or [{"kind": "stable", "message": "No material review-level changes detected."}]


def rank_likely_issue_tracks(
    *,
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    changed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        kind = str(item.get("kind", "finding"))
        by_kind.setdefault(kind, []).append(item)
    for idx, (kind, items) in enumerate(sorted(by_kind.items()), start=1):
        top_priority = max(int(entry.get("priority", 0)) for entry in items)
        tracks.append(
            {
                "track_id": f"track-{idx}:{kind}",
                "track": f"{kind}-stabilization",
                "likelihood": round(min(0.95, 0.25 + (top_priority / 120.0) + (len(items) * 0.05)), 2),
                "priority": top_priority,
                "supporting_evidence": [
                    {
                        "id": str(entry.get("id", "")),
                        "message": str(entry.get("message", "")),
                        "priority": int(entry.get("priority", 0)),
                    }
                    for entry in sorted(items, key=lambda row: -int(row.get("priority", 0)))[:3]
                ],
                "conflicting_evidence": [
                    {"id": str(conflict.get("id", "")), "message": str(conflict.get("message", ""))}
                    for conflict in conflicts[:3]
                ],
                "verification_steps": [
                    "Re-run targeted review workflow for this track after remediation.",
                    "Confirm healthy controls remain preserved after applying changes.",
                ],
                "recommended_next_moves": [
                    str(items[0].get("next_action", "Investigate and remediate top evidence on this track."))
                ],
                "blockers": ["Conflicting evidence unresolved." if conflicts else "No active blockers currently detected."],
            }
        )
    if not tracks:
        tracks.append(
            {
                "track_id": "track-0:control-integrity",
                "track": "control-integrity",
                "likelihood": 0.2,
                "priority": 10,
                "supporting_evidence": [{"id": "baseline", "message": "No high-signal findings in baseline layer.", "priority": 0}],
                "conflicting_evidence": [],
                "verification_steps": ["Run lightweight spot-checks on recent changed areas."],
                "recommended_next_moves": ["Continue with monitor-tier controls and next scheduled review."],
                "blockers": [],
            }
        )
    if changed:
        tracks[0]["historical_context"] = changed[:3]
    return sorted(tracks, key=lambda item: (-int(item.get("priority", 0)), str(item.get("track_id", ""))))[:5]
