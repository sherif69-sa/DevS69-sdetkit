from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProbeDefinition:
    probe_id: str
    requires: str
    min_score: int
    cost: int
    max_chain_depth: int
    bounded_contract: dict[str, Any]
    reason: str


def _round2(value: float) -> float:
    return round(float(value), 2)


def derive_probe_score_history_inputs(
    *,
    probe_id: str,
    probe_memory: dict[str, Any] | None,
    current_track: str,
) -> tuple[list[dict[str, Any]], int]:
    memory = probe_memory if isinstance(probe_memory, dict) else {}
    probes = memory.get("probes", {})
    probe_stats = probes.get(probe_id, {}) if isinstance(probes, dict) else {}
    aggregates = probe_stats.get("aggregates", {}) if isinstance(probe_stats, dict) else {}
    has_history = int(aggregates.get("runs", 0)) > 0
    avg_usefulness = float(aggregates.get("avg_usefulness", 0.0))
    avg_cost = float(aggregates.get("avg_cost", 0.0))
    saturation = float(aggregates.get("repeat_hit_saturation", 0.0))
    track_payoff_map = aggregates.get("track_payoff", {}) if isinstance(aggregates, dict) else {}
    track_payoff = float(
        track_payoff_map.get(current_track, avg_usefulness if avg_usefulness > 0 else 0.5)
    )

    usefulness_delta = int(round((avg_usefulness - 0.5) * 40)) if has_history else 0
    cost_penalty = int(round((avg_cost / 100.0) * 12)) if has_history else 0
    saturation_penalty = int(round(saturation * 18)) if has_history else 0
    track_delta = int(round((track_payoff - 0.5) * 20)) if has_history else 0
    history_delta = usefulness_delta + track_delta - cost_penalty - saturation_penalty
    score_inputs = [
        {
            "input": "history_avg_usefulness",
            "value": _round2(avg_usefulness),
            "weight": "((value-0.5)*40)",
        },
        {"input": "history_avg_cost", "value": _round2(avg_cost), "weight": "-((value/100)*12)"},
        {
            "input": "history_repeat_hit_saturation",
            "value": _round2(saturation),
            "weight": "-(value*18)",
        },
        {
            "input": f"history_track_payoff[{current_track}]",
            "value": _round2(track_payoff),
            "weight": "((value-0.5)*20)",
        },
        {"input": "history_net_delta", "value": history_delta, "weight": "derived"},
    ]
    return score_inputs, history_delta


def normalize_probe_execution_outcomes(
    *,
    executed_probes: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_count = len(findings)
    conflicts_count = len(conflicts)
    context_track = "risk_pressure" if findings_count > 0 or conflicts_count > 0 else "stability"
    normalized: list[dict[str, Any]] = []
    for probe in sorted(executed_probes, key=lambda row: str(row.get("probe_id", ""))):
        if not isinstance(probe, dict):
            continue
        if str(probe.get("status", "")) != "executed":
            continue
        probe_id = str(probe.get("probe_id", "probe:unknown"))
        result = str(probe.get("result", "unknown"))
        cost = int(probe.get("cost", 0))
        if result == "findings":
            usefulness = 0.85 if findings_count > 0 or conflicts_count > 0 else 0.7
        elif result == "ok":
            usefulness = 0.7 if findings_count == 0 and conflicts_count == 0 else 0.45
        else:
            usefulness = 0.3
        normalized.append(
            {
                "probe_id": probe_id,
                "result": result,
                "status": "executed",
                "cost": cost,
                "usefulness": _round2(usefulness),
                "cost_normalized": _round2(min(1.0, max(0.0, cost / 100.0))),
                "hit_key": f"{result}:{context_track}",
                "context_track": context_track,
            }
        )
    return normalized


def apply_probe_memory_update(
    *,
    previous_memory: dict[str, Any] | None,
    normalized_outcomes: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    memory: dict[str, Any] = {"schema_version": "sdetkit.review.probe-memory.v1", "probes": {}}
    if isinstance(previous_memory, dict):
        memory["probes"] = (
            previous_memory.get("probes", {})
            if isinstance(previous_memory.get("probes"), dict)
            else {}
        )
    probes = memory["probes"]
    run_updates: list[dict[str, Any]] = []
    for outcome in sorted(normalized_outcomes, key=lambda item: str(item.get("probe_id", ""))):
        probe_id = str(outcome.get("probe_id", "probe:unknown"))
        probe_entry = probes.get(probe_id, {}) if isinstance(probes.get(probe_id), dict) else {}
        history = probe_entry.get("outcomes", [])
        if not isinstance(history, list):
            history = []
        history = [row for row in history if isinstance(row, dict)]
        history.append(outcome)
        history = history[-30:]

        uses = [float(row.get("usefulness", 0.0)) for row in history]
        costs = [int(row.get("cost", 0)) for row in history]
        avg_usefulness = _round2(sum(uses) / len(uses))
        avg_cost = _round2(sum(costs) / len(costs))

        tail_result = str(history[-1].get("result", "unknown"))
        repeat_hits = 1
        for row in reversed(history[:-1]):
            if str(row.get("result", "")) == tail_result:
                repeat_hits += 1
            else:
                break
        saturation = _round2(min(1.0, max(0.0, (repeat_hits - 1) / 3.0)))

        track_buckets: dict[str, list[float]] = {}
        for row in history:
            track = str(row.get("context_track", "stability"))
            track_buckets.setdefault(track, []).append(float(row.get("usefulness", 0.0)))
        track_payoff = {
            track: _round2(sum(values) / len(values))
            for track, values in sorted(track_buckets.items())
        }

        aggregates = {
            "runs": len(history),
            "avg_usefulness": avg_usefulness,
            "avg_cost": avg_cost,
            "repeat_hit_result": tail_result,
            "repeat_hit_count": repeat_hits,
            "repeat_hit_saturation": saturation,
            "track_payoff": track_payoff,
        }
        probe_entry["outcomes"] = history
        probe_entry["aggregates"] = aggregates
        probes[probe_id] = probe_entry
        run_updates.append(
            {"probe_id": probe_id, "aggregates": aggregates, "latest_outcome": outcome}
        )

    summary = {
        "normalized_outcomes": normalized_outcomes,
        "updates": run_updates,
    }
    return memory, summary


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


def build_staged_plan(
    *, profile_name: str, stages: tuple[Any, ...], workflow_plan: dict[str, bool]
) -> dict[str, Any]:
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
    can_stop = (
        final_confidence >= confidence_threshold and findings_count == 0 and conflicts_count == 0
    )
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
        key=lambda item: (
            str(item.get("kind", "")),
            str(item.get("id", "")),
            str(item.get("message", "")),
        ),
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
    budget_total: int = 100,
    confidence_score: float = 0.0,
    confidence_threshold: float = 0.7,
    probe_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contradictory = len(contradiction_graph.get("flat_contradictions", []))
    cluster_pressure = len(contradiction_graph.get("clusters", []))
    finding_pressure = sum(max(0, int(item.get("priority", 0))) for item in findings)
    history_pressure = len(
        [row for row in changed if str(row.get("kind")) in {"status", "severity"}]
    )
    current_track = "risk_pressure" if contradictory > 0 or finding_pressure > 0 else "stability"
    registry = [
        ProbeDefinition(
            probe_id="probe:inspect-compare",
            requires="inspect_compare_available",
            min_score=25,
            cost=55,
            max_chain_depth=2,
            bounded_contract={
                "max_runtime_seconds": 20,
                "max_artifacts": 2,
                "max_input_payloads": 2,
            },
            reason="Resolve whether recent evidence drift explains current contradictions/findings.",
        ),
        ProbeDefinition(
            probe_id="probe:workspace-history",
            requires="workspace_like",
            min_score=25,
            cost=30,
            max_chain_depth=2,
            bounded_contract={
                "max_runtime_seconds": 10,
                "max_artifacts": 1,
                "max_manifest_entries": 200,
            },
            reason="Use repeated-run history to verify whether risk is persistent or newly introduced.",
        ),
    ]
    candidates: list[dict[str, Any]] = []
    for probe in registry:
        score = 0
        score_inputs: list[dict[str, Any]] = []
        if probe.probe_id == "probe:inspect-compare":
            score += 35 if contradictory else 0
            score_inputs.append(
                {"input": "contradictions_present", "value": contradictory, "weight": 35}
            )
            score += cluster_pressure * 12
            score_inputs.append(
                {"input": "cluster_pressure", "value": cluster_pressure, "weight": 12}
            )
            score += finding_pressure // 6
            score_inputs.append(
                {"input": "finding_pressure", "value": finding_pressure, "weight": "1/6"}
            )
            score += 15 if has_previous_review else 0
            score_inputs.append(
                {"input": "has_previous_review", "value": has_previous_review, "weight": 15}
            )
        elif probe.probe_id == "probe:workspace-history":
            score += 20 if contradictory else 0
            score_inputs.append(
                {"input": "contradictions_present", "value": contradictory, "weight": 20}
            )
            score += history_pressure * 20
            score_inputs.append(
                {"input": "history_pressure", "value": history_pressure, "weight": 20}
            )
            score += 10 if profile_name == "forensics" else 0
            score_inputs.append(
                {"input": "forensics_profile", "value": profile_name == "forensics", "weight": 10}
            )
            score += 8 if confidence_score < confidence_threshold else 0
            score_inputs.append(
                {
                    "input": "confidence_gap",
                    "value": round(confidence_threshold - confidence_score, 2),
                    "weight": 8,
                }
            )
        history_inputs, history_delta = derive_probe_score_history_inputs(
            probe_id=probe.probe_id,
            probe_memory=probe_memory,
            current_track=current_track,
        )
        score += history_delta
        score_inputs.extend(history_inputs)
        candidates.append(
            {
                "probe_id": probe.probe_id,
                "requires": probe.requires,
                "score": score,
                "score_inputs": score_inputs,
                "reason": probe.reason,
                "cost": probe.cost,
                "min_score": probe.min_score,
                "max_chain_depth": probe.max_chain_depth,
                "bounded_contract": probe.bounded_contract,
            }
        )
    executed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    budget_spent = 0
    chain_depth = 0
    chain_enabled = contradictory > 0 or cluster_pressure > 0
    for row in sorted(candidates, key=lambda item: (-int(item["score"]), str(item["probe_id"]))):
        requires = str(row["requires"])
        enabled = (
            bool(detection.get("workspace_like"))
            if requires == "workspace_like"
            else bool(detection.get("data_like"))
        )
        affordable = (budget_spent + int(row["cost"])) <= budget_total
        enough_score = int(row["score"]) >= int(row["min_score"])
        within_chain = chain_depth < int(row["max_chain_depth"])
        should_run = (
            enabled and enough_score and len(executed) < max_probes and affordable and within_chain
        )
        target = executed if should_run else skipped
        if should_run:
            budget_spent += int(row["cost"])
            chain_depth += 1 if chain_enabled else 0
        skip_reason = ""
        if not should_run:
            if not enabled:
                skip_reason = "probe preconditions missing"
            elif not enough_score:
                skip_reason = "probe score below deterministic minimum"
            elif not affordable:
                skip_reason = "probe budget exhausted by higher-value probes"
            elif not within_chain:
                skip_reason = "probe chain depth limit reached"
            else:
                skip_reason = "probe count limit reached"
        target.append(
            {
                "probe_id": row["probe_id"],
                "score": int(row["score"]),
                "reason": row["reason"],
                "requires": requires,
                "status": "planned" if should_run else "skipped",
                "skip_reason": skip_reason,
                "score_inputs": row["score_inputs"],
                "cost": int(row["cost"]),
                "budget_before": budget_spent - int(row["cost"]) if should_run else budget_spent,
                "budget_after": budget_spent if should_run else budget_spent,
                "bounded_contract": row["bounded_contract"],
                "chain": {
                    "enabled": chain_enabled,
                    "step": chain_depth if should_run else None,
                    "max_depth": int(row["max_chain_depth"]),
                },
            }
        )
    return {
        "executed_probes": executed,
        "skipped_probes": skipped,
        "registry": [
            {
                "probe_id": row["probe_id"],
                "requires": row["requires"],
                "min_score": int(row["min_score"]),
                "cost": int(row["cost"]),
                "bounded_contract": row["bounded_contract"],
            }
            for row in sorted(candidates, key=lambda item: str(item["probe_id"]))
        ],
        "budget": {
            "total": budget_total,
            "spent": budget_spent,
            "remaining": max(0, budget_total - budget_spent),
            "max_probes": max_probes,
            "chain_enabled": chain_enabled,
            "stop_reason": (
                "budget exhausted"
                if budget_spent >= budget_total
                else "confidence sufficient"
                if confidence_score >= confidence_threshold
                else "probe selection completed"
            ),
        },
    }


def build_typed_evidence_edges(
    *,
    executed_probes: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for probe in executed_probes:
        if not isinstance(probe, dict):
            continue
        probe_id = str(probe.get("probe_id", "probe:unknown"))
        result = str(probe.get("result", "unknown"))
        if conflicts:
            for conflict in conflicts[:2]:
                edges.append(
                    {
                        "edge_id": f"{probe_id}->{conflict.get('id', 'conflict:unknown')}",
                        "relation": "conflicts",
                        "from": probe_id,
                        "to": str(conflict.get("id", "conflict:unknown")),
                        "why": "Probe result observed contradictory signal pressure.",
                    }
                )
        if findings and result == "findings":
            for finding in findings[:2]:
                edges.append(
                    {
                        "edge_id": f"{probe_id}->{finding.get('id', 'finding:unknown')}",
                        "relation": "supports",
                        "from": probe_id,
                        "to": str(finding.get("id", "finding:unknown")),
                        "why": "Probe result reinforced an active finding.",
                    }
                )
        if tracks and result == "ok":
            first_track = tracks[0]
            if isinstance(first_track, dict):
                edges.append(
                    {
                        "edge_id": f"{probe_id}->{first_track.get('track_id', 'track:unknown')}",
                        "relation": "neutral",
                        "from": probe_id,
                        "to": str(first_track.get("track_id", "track:unknown")),
                        "why": "Probe completed without adding risk pressure.",
                    }
                )
    return sorted(edges, key=lambda item: str(item.get("edge_id", "")))


def apply_probe_result_feedback(
    *,
    findings: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    likely_tracks: list[dict[str, Any]],
    executed_probes: list[dict[str, Any]],
) -> dict[str, Any]:
    probe_pressure = len(executed_probes)
    confidence_delta = (
        0.08 if probe_pressure > 0 and not findings and not conflicts else -0.03 * probe_pressure
    )
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


def summarize_history_delta(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(previous, dict):
        return [{"kind": "baseline", "message": "No previous review run found for this scope."}]
    changes: list[dict[str, Any]] = []
    prev_actions = previous.get("prioritized_actions", [])
    cur_actions = current.get("prioritized_actions", [])
    prev_now = len([a for a in prev_actions if isinstance(a, dict) and a.get("tier") == "now"])
    cur_now = len([a for a in cur_actions if isinstance(a, dict) and a.get("tier") == "now"])
    if prev_now != cur_now:
        changes.append(
            {
                "kind": "action_pressure",
                "message": f"immediate_actions changed {prev_now} -> {cur_now}",
            }
        )
    prev_status = str(previous.get("status", ""))
    cur_status = str(current.get("status", ""))
    if prev_status != cur_status:
        changes.append(
            {"kind": "status", "message": f"status changed {prev_status} -> {cur_status}"}
        )
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
                "likelihood": round(
                    min(0.95, 0.25 + (top_priority / 120.0) + (len(items) * 0.05)), 2
                ),
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
                    str(
                        items[0].get(
                            "next_action", "Investigate and remediate top evidence on this track."
                        )
                    )
                ],
                "blockers": [
                    "Conflicting evidence unresolved."
                    if conflicts
                    else "No active blockers currently detected."
                ],
            }
        )
    if not tracks:
        tracks.append(
            {
                "track_id": "track-0:control-integrity",
                "track": "control-integrity",
                "likelihood": 0.2,
                "priority": 10,
                "supporting_evidence": [
                    {
                        "id": "baseline",
                        "message": "No high-signal findings in baseline layer.",
                        "priority": 0,
                    }
                ],
                "conflicting_evidence": [],
                "verification_steps": ["Run lightweight spot-checks on recent changed areas."],
                "recommended_next_moves": [
                    "Continue with monitor-tier controls and next scheduled review."
                ],
                "blockers": [],
            }
        )
    if changed:
        tracks[0]["historical_context"] = changed[:3]
    return sorted(
        tracks, key=lambda item: (-int(item.get("priority", 0)), str(item.get("track_id", "")))
    )[:5]


ERROR_TRIAGE_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "ruff-import-order",
        "match": "I001",
        "category": "lint",
        "recommendation": "Run `python -m ruff check --fix <paths>` then re-run `python -m ruff check src tests`.",
    },
    {
        "id": "ruff-unused-import",
        "match": "F401",
        "category": "lint",
        "recommendation": "Remove unused imports or run `python -m ruff check --fix <paths>` and re-run lint.",
    },
    {
        "id": "repo-trailing-whitespace",
        "match": "trailing_whitespace",
        "category": "repo-hygiene",
        "recommendation": "Strip trailing spaces in flagged files, then run `python -m sdetkit repo check --format json --force`.",
    },
    {
        "id": "gha-unpinned-action",
        "match": "unpinned_action",
        "category": "security",
        "recommendation": "Pin GitHub Actions to full commit SHAs and verify with enterprise repo check profile.",
    },
    {
        "id": "wheel-not-found",
        "match": "*.whl is not a valid wheel filename",
        "category": "packaging",
        "recommendation": "Build wheel first (`python -m build`) and install using an explicit discovered wheel path.",
    },
    {
        "id": "gate-problems-found",
        "match": "gate: problems found",
        "category": "quality-gate",
        "recommendation": "Open gate JSON artifact, inspect `failed_steps`, fix top failing step, then rerun gate.",
    },
)


def triage_error_log(text: str) -> dict[str, Any]:
    lowered = text.lower()
    hits: list[dict[str, Any]] = []
    for rule in ERROR_TRIAGE_RULES:
        marker = str(rule["match"]).lower()
        if marker in lowered:
            hits.append(
                {
                    "id": rule["id"],
                    "category": rule["category"],
                    "match": rule["match"],
                    "recommendation": rule["recommendation"],
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in hits:
        rid = str(row["id"])
        if rid in seen:
            continue
        seen.add(rid)
        deduped.append(row)

    return {
        "schema_version": "sdetkit.review.error-triage.v1",
        "matched_rules": deduped,
        "summary": {
            "matches": len(deduped),
            "ok": len(deduped) == 0,
        },
    }
