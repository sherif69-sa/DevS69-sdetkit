from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.judgment.v1"

_SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

JUDGMENT_GUIDELINES: tuple[dict[str, str], ...] = (
    {
        "id": "guideline-contradictions-first",
        "when": "conflicting evidence exists",
        "judgment": "force now-tier contradiction resolution before promotion",
    },
    {
        "id": "guideline-blocking-risk",
        "when": "status is fail or priority pressure is high",
        "judgment": "treat as fail and prioritize immediate remediation",
    },
    {
        "id": "guideline-watch-low-confidence",
        "when": "status is watch with low confidence",
        "judgment": "continue monitor lane and gather more evidence",
    },
    {
        "id": "guideline-pass-high-confidence",
        "when": "status is pass with high confidence",
        "judgment": "allow promotion and keep routine monitoring",
    },
    {
        "id": "guideline-pass-cautious",
        "when": "status is pass with non-high confidence",
        "judgment": "allow promotion with explicit follow-up checks",
    },
)


def _select_guideline(*, status: str, priority_score: int, confidence_level: str, has_contradictions: bool) -> dict[str, str]:
    if has_contradictions:
        return dict(JUDGMENT_GUIDELINES[0])
    if status == "fail" or priority_score >= 60:
        return dict(JUDGMENT_GUIDELINES[1])
    if status == "watch" and confidence_level == "low":
        return dict(JUDGMENT_GUIDELINES[2])
    if status == "pass" and confidence_level == "high":
        return dict(JUDGMENT_GUIDELINES[3])
    return dict(JUDGMENT_GUIDELINES[4])



def _severity_from_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _level_from_confidence(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _status(*, workflow_ok: bool, priority_score: int, blocking: bool) -> str:
    if workflow_ok:
        return "pass"
    if blocking or priority_score >= 60:
        return "fail"
    return "watch"


def _top_findings(findings: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            -int(item.get("priority", 0)),
            -_SEVERITY_ORDER.get(str(item.get("severity", "low")), 0),
            str(item.get("kind", "")),
        ),
    )[:limit]


def _build_confidence(*, completeness: float, consistency: float, stability: float, drivers: list[str]) -> dict[str, Any]:
    score = max(0.0, min(1.0, round((completeness * 0.4) + (consistency * 0.4) + (stability * 0.2), 2)))
    return {
        "score": score,
        "level": _level_from_confidence(score),
        "drivers": drivers,
    }


def _recommendations_from_findings(findings: list[dict[str, Any]], *, contradictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for idx, finding in enumerate(_top_findings(findings, limit=5), start=1):
        priority = int(finding.get("priority", 0))
        tier = "monitor"
        if priority >= 60:
            tier = "now"
        elif priority >= 30:
            tier = "next"
        recs.append(
            {
                "id": f"rec-{idx}",
                "tier": tier,
                "priority": priority,
                "action": str(finding.get("next_action", "Investigate high-signal evidence and update controls.")),
                "rationale": str(finding.get("why_it_matters", "High-signal finding requires follow-up.")),
                "depends_on": list(finding.get("depends_on", [])),
            }
        )
    if contradictions:
        recs.insert(
            0,
            {
                "id": "rec-contradictions",
                "tier": "now",
                "priority": 70,
                "action": "Resolve conflicting evidence before promotion decisions.",
                "rationale": "Signals disagree across surfaces, reducing trust in a single-pass decision.",
                "depends_on": [str(item.get("id", "")) for item in contradictions],
            },
        )
    return recs[:6]


def build_judgment(
    *,
    workflow: str,
    findings: list[dict[str, Any]],
    supporting_evidence: list[dict[str, Any]],
    conflicting_evidence: list[dict[str, Any]],
    completeness: float,
    stability: float,
    previous_summary: str | None = None,
    workflow_ok: bool = True,
    blocking: bool = False,
) -> dict[str, Any]:
    contradictions = conflicting_evidence[:5]
    top = _top_findings(findings)
    priority_score = min(100, sum(int(item.get("priority", 0)) for item in top))
    consistency = 1.0
    if supporting_evidence or conflicting_evidence:
        consistency = len(supporting_evidence) / max(1, len(supporting_evidence) + len(conflicting_evidence))
    drivers = [
        f"completeness={round(completeness, 2)}",
        f"consistency={round(consistency, 2)}",
        f"stability={round(stability, 2)}",
    ]
    if previous_summary:
        drivers.append(f"previous={previous_summary}")
    confidence = _build_confidence(
        completeness=completeness,
        consistency=consistency,
        stability=stability,
        drivers=drivers,
    )
    status = _status(workflow_ok=workflow_ok, priority_score=priority_score, blocking=blocking)
    severity = _severity_from_score(priority_score)
    if status == "pass":
        severity = "low"
    elif status == "fail" and severity in {"low", "medium"}:
        severity = "high"
    recommendations = _recommendations_from_findings(top, contradictions=contradictions)
    what_matters = [
        {
            "kind": str(item.get("kind", "finding")),
            "priority": int(item.get("priority", 0)),
            "message": str(item.get("why_it_matters", item.get("message", ""))),
        }
        for item in top
    ]
    next_move = recommendations[0]["action"] if recommendations else "No immediate action required."
    guideline = _select_guideline(
        status=status,
        priority_score=priority_score,
        confidence_level=str(confidence.get("level", "low")),
        has_contradictions=bool(contradictions),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": workflow,
        "status": status,
        "severity": severity,
        "priority_score": priority_score,
        "contract_alignment": {
            "workflow_ok": workflow_ok,
            "blocking": blocking,
            "rule": "pass=>ok true; non-ok => watch/fail based on blocking severity",
        },
        "summary": (
            "No high-signal blockers detected."
            if status == "pass"
            else "High-signal risk detected; prioritize targeted remediation."
            if status == "fail"
            else "Mixed signal set detected; monitor closely and remediate top risks."
        ),
        "top_judgment": {
            "what_matters_most": what_matters,
            "why": "Signals are ranked by severity, drift impact, and cross-surface relevance.",
            "next_move": next_move,
        },
        "findings": top,
        "evidence": {
            "supporting": supporting_evidence[:20],
            "conflicting": conflicting_evidence[:20],
            "coverage": {"completeness": round(completeness, 2)},
            "stability": {"score": round(stability, 2), "has_previous": bool(previous_summary)},
        },
        "contradictions": contradictions,
        "confidence": confidence,
        "judgment_guideline": guideline,
        "guideline_catalog": list(JUDGMENT_GUIDELINES),
        "recommendations": recommendations,
    }


def load_latest_previous_payload(*, workspace_root: Path, workflow: str, scope: str) -> tuple[dict[str, Any] | None, str | None]:
    manifest_path = workspace_root / "manifest.json"
    if not manifest_path.exists():
        return None, None
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    runs = loaded.get("runs", [])
    if not isinstance(runs, list):
        return None, None
    filtered = [
        item
        for item in runs
        if isinstance(item, dict)
        and str(item.get("workflow", "")) == workflow
        and str(item.get("scope", "")) == scope
    ]
    if not filtered:
        return None, None
    latest = sorted(filtered, key=lambda item: (int(item.get("run_order", 0)), str(item.get("run_hash", ""))))[-1]
    record_path = workspace_root / str(latest.get("record_path", ""))
    if not record_path.exists():
        return None, None
    record = json.loads(record_path.read_text(encoding="utf-8"))
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None, None
    return payload, str(latest.get("run_hash", ""))
