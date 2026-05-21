from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.reliability_spine_alignment.v1"

SPINE_STAGES = (
    "evidence",
    "diagnosis",
    "decision",
    "remediation_eligibility",
    "proof",
    "trajectory",
    "reporting",
    "history",
    "verifier",
    "benchmark",
)

VALID_STATUSES = {
    "aligned",
    "partially_aligned",
    "planned",
    "needs_review",
}

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class AlignmentComponent:
    module: str
    role: str
    status: str
    stages: tuple[str, ...]
    existing_artifacts: tuple[str, ...]
    integration_points: tuple[str, ...]
    gaps: tuple[str, ...]
    recommended_next_action: str


def _component(
    *,
    module: str,
    role: str,
    status: str,
    stages: tuple[str, ...],
    existing_artifacts: tuple[str, ...] = (),
    integration_points: tuple[str, ...] = (),
    gaps: tuple[str, ...] = (),
    recommended_next_action: str = "keep aligned with the reliability spine",
) -> AlignmentComponent:
    if status not in VALID_STATUSES:
        msg = f"invalid alignment status for {module}: {status}"
        raise ValueError(msg)

    unknown_stages = sorted(set(stages) - set(SPINE_STAGES))
    if unknown_stages:
        msg = f"invalid spine stages for {module}: {', '.join(unknown_stages)}"
        raise ValueError(msg)

    return AlignmentComponent(
        module=module,
        role=role,
        status=status,
        stages=stages,
        existing_artifacts=existing_artifacts,
        integration_points=integration_points,
        gaps=gaps,
        recommended_next_action=recommended_next_action,
    )


def build_alignment_components() -> list[AlignmentComponent]:
    return [
        _component(
            module="failed_check_log_collection",
            role="collect failed check logs and make raw CI evidence available",
            status="aligned",
            stages=("evidence",),
            existing_artifacts=("failed-check-logs", "download-failed-check-logs.sh"),
            integration_points=("check_intelligence", "PR Quality workflow"),
            recommended_next_action="keep as the CI log collection entry point",
        ),
        _component(
            module="check_intelligence",
            role="normalize checks, logs, security review, and code scanning into action reports",
            status="aligned",
            stages=("evidence", "diagnosis", "decision", "reporting"),
            existing_artifacts=("check-intelligence.json", "action-report.json"),
            integration_points=(
                "pr_quality_action_report",
                "evidence_graph",
                "trajectory_store",
            ),
            recommended_next_action="continue hardening exact first-failure extraction",
        ),
        _component(
            module="diagnostic_vector_engine",
            role="produce canonical diagnostic and failure vectors",
            status="aligned",
            stages=("evidence", "diagnosis", "trajectory"),
            existing_artifacts=("diagnostic-vector.json", "failure-vector.json"),
            integration_points=("remediation_plan_engine", "trajectory_store"),
            recommended_next_action="feed future PatchScorer and verifier decisions",
        ),
        _component(
            module="remediation_plan_engine",
            role="plan review-first and safe-fix remediation routes",
            status="partially_aligned",
            stages=("decision", "remediation_eligibility", "proof"),
            existing_artifacts=("remediation plans",),
            integration_points=("diagnostic_vector_engine", "trajectory_store"),
            gaps=(
                "needs stronger feedback from trajectory history",
                "needs PatchScorer before broader mutation use",
            ),
            recommended_next_action="connect plan decisions to PatchScorer and protected proof",
        ),
        _component(
            module="safe_remediation_eligibility",
            role="decide whether a failed surface is eligible for narrow mechanical remediation",
            status="aligned",
            stages=("decision", "remediation_eligibility"),
            integration_points=("check_intelligence", "maintenance_autopilot"),
            recommended_next_action="keep unknown, security, release, and dependency cases review-first",
        ),
        _component(
            module="maintenance_autopilot",
            role="bridge approved safe formatting fixes into PR branches",
            status="partially_aligned",
            stages=("remediation_eligibility", "proof"),
            integration_points=("check_intelligence", "safe_remediation_eligibility"),
            gaps=(
                "should remain formatting-only until PatchScorer exists",
                "needs ProtectedVerifier before broader automation",
            ),
            recommended_next_action="do not expand beyond approved safe formatting fixes yet",
        ),
        _component(
            module="pr_quality_evidence_narrative",
            role="explain quality, evidence graph, and changed-file signals",
            status="aligned",
            stages=("evidence", "reporting"),
            existing_artifacts=("pr-evidence-narrative.json", "pr-evidence-narrative.md"),
            integration_points=("pr_quality_action_report", "trajectory_store"),
            recommended_next_action="keep evidence-review and proof-signal semantics explicit",
        ),
        _component(
            module="evidence_graph",
            role="connect sentinel, failure bundle, and PR Quality evidence into review/proof signals",
            status="aligned",
            stages=("evidence", "diagnosis", "decision"),
            existing_artifacts=("evidence-graph.json",),
            integration_points=("pr_quality_evidence_narrative", "operator_evidence_loop"),
            recommended_next_action="use graph signals as durable trajectory inputs",
        ),
        _component(
            module="pr_quality_action_report",
            role="render operator-facing PR Quality status, evidence, and trajectory summaries",
            status="aligned",
            stages=("reporting", "trajectory"),
            existing_artifacts=("pr-comment-body.md", "pr-comment-metadata.json"),
            integration_points=("check_intelligence", "trajectory_store"),
            recommended_next_action="keep comments action-focused and non-educational",
        ),
        _component(
            module="trajectory_store",
            role="record action, response, diagnosis, decision, fix, proof, and result",
            status="aligned",
            stages=("trajectory", "decision", "proof"),
            existing_artifacts=("trajectory.jsonl",),
            integration_points=(
                "diagnostic_vector_engine",
                "pr_quality_action_report",
                "trajectory_history_report",
            ),
            recommended_next_action="remain local-first and deterministic",
        ),
        _component(
            module="trajectory_history_report",
            role="summarize trajectory records by final result, risk surface, class, and action",
            status="aligned",
            stages=("history", "reporting"),
            existing_artifacts=("trajectory history JSON/Markdown reports",),
            integration_points=("trajectory_store",),
            recommended_next_action="feed future pattern insights and RepoMemory",
        ),
        _component(
            module="current_head_failure_bundle",
            role="capture current-head failure evidence for operator inspection",
            status="partially_aligned",
            stages=("evidence", "reporting"),
            existing_artifacts=("current-head failure bundle",),
            integration_points=("pr_quality_action_report",),
            gaps=("should include or link trajectory records for the same head SHA",),
            recommended_next_action="connect bundle summaries to trajectory/history reports",
        ),
        _component(
            module="operator_evidence_loop",
            role="assemble verified operator evidence loop outputs",
            status="partially_aligned",
            stages=("evidence", "diagnosis", "decision", "reporting"),
            integration_points=("evidence_graph", "pr_quality_action_report"),
            gaps=(
                "should consume trajectory history",
                "should later include PatchScorer and ProtectedVerifier results",
            ),
            recommended_next_action="make it the local orchestration report after PatchScorer exists",
        ),
        _component(
            module="security_review_evidence",
            role="collect and summarize unresolved security review findings",
            status="aligned",
            stages=("evidence", "decision", "reporting"),
            integration_points=("check_intelligence", "pr_quality_action_report"),
            recommended_next_action="keep security findings review-first",
        ),
        _component(
            module="adaptive_diagnosis",
            role="classify log symptoms into diagnostic candidates",
            status="partially_aligned",
            stages=("diagnosis",),
            integration_points=("check_intelligence",),
            gaps=(
                "needs stronger exact-failure extraction feedback",
                "should emit confidence and uncertainty consistently",
            ),
            recommended_next_action="harden unknown-failure classification without broad automation",
        ),
        _component(
            module="PatchScorer",
            role="score proposed patches for safety before trusting them",
            status="planned",
            stages=("decision", "proof", "verifier"),
            gaps=(
                "not implemented yet",
                "needed before expanding safe remediation beyond formatting",
            ),
            recommended_next_action="build local prototype after pattern insights",
        ),
        _component(
            module="ProtectedVerifier",
            role="prove fixes without weakening tests, CI, security, or public behavior",
            status="planned",
            stages=("proof", "verifier"),
            gaps=("not implemented yet",),
            recommended_next_action="build after PatchScorer prototype",
        ),
        _component(
            module="ReplayableBenchmarkHarness",
            role="run local remediation scenarios with oracle/pass and nop/fail checks",
            status="planned",
            stages=("benchmark", "proof", "verifier"),
            gaps=("not implemented yet",),
            recommended_next_action="build after ProtectedVerifier has a local contract",
        ),
        _component(
            module="RepoMemory",
            role="persist repeated failure patterns and proven decisions",
            status="planned",
            stages=("history", "decision"),
            gaps=("not implemented yet", "should remain local-first initially"),
            recommended_next_action="build after trajectory pattern insights are proven",
        ),
    ]


def _component_payload(component: AlignmentComponent) -> JsonObject:
    payload = asdict(component)
    return {
        key: list(value) if isinstance(value, tuple) else value for key, value in payload.items()
    }


def build_alignment_report(
    components: list[AlignmentComponent] | None = None,
) -> JsonObject:
    rows = components or build_alignment_components()
    status_counts = Counter(component.status for component in rows)
    stage_counts: Counter[str] = Counter()
    for component in rows:
        stage_counts.update(component.stages)

    gaps = [
        {
            "module": component.module,
            "gaps": list(component.gaps),
            "recommended_next_action": component.recommended_next_action,
        }
        for component in rows
        if component.gaps
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "component_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "stage_counts": dict(sorted(stage_counts.items())),
        "components": [_component_payload(component) for component in rows],
        "gaps": gaps,
        "next_recommended_pr": "feature/trajectory-pattern-insights",
    }


def render_alignment_markdown(report: Mapping[str, Any]) -> str:
    components = [_as_dict(item) for item in _as_list(report.get("components"))]
    gaps = [_as_dict(item) for item in _as_list(report.get("gaps"))]

    lines = [
        "# Reliability spine alignment audit",
        "",
        f"- Schema: `{report.get('schema_version', '')}`",
        f"- Components: `{int(report.get('component_count', 0) or 0)}`",
        f"- Next recommended PR: `{report.get('next_recommended_pr', '')}`",
        "",
        "## Status counts",
        "",
    ]

    status_counts = _as_dict(report.get("status_counts"))
    if status_counts:
        lines.extend(f"- `{status}`: `{count}`" for status, count in status_counts.items())
    else:
        lines.append("- none")

    lines.extend(["", "## Stage counts", ""])
    stage_counts = _as_dict(report.get("stage_counts"))
    if stage_counts:
        lines.extend(f"- `{stage}`: `{count}`" for stage, count in stage_counts.items())
    else:
        lines.append("- none")

    lines.extend(["", "## Components", ""])
    for component in components:
        stages = ", ".join(f"`{stage}`" for stage in _as_list(component.get("stages")))
        lines.append(
            f"- `{component.get('module', '')}`: "
            f"`{component.get('status', '')}` — {component.get('role', '')}"
        )
        lines.append(f"  - Stages: {stages or '`none`'}")
        lines.append(f"  - Next: {component.get('recommended_next_action', '')}")

    lines.extend(["", "## Gaps", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- `{gap.get('module', '')}`")
            for item in _as_list(gap.get("gaps")):
                lines.append(f"  - {item}")
            lines.append(f"  - Next: {gap.get('recommended_next_action', '')}")
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def write_alignment_report(
    *,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> JsonObject:
    report = build_alignment_report()

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if markdown_out is not None:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(render_alignment_markdown(report), encoding="utf-8")

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.reliability_spine_alignment")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = write_alignment_report(
        json_out=args.json_out,
        markdown_out=args.markdown_out,
    )

    if args.format == "json":
        print(json.dumps({"report": report}, indent=2, sort_keys=True))
    else:
        print(render_alignment_markdown(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
