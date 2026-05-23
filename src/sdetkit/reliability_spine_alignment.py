from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.reliability_spine_alignment.v1"
PR_QUALITY_LIVE_WORKSPACE_MODULE = "_".join(("pr", "quality", "live", "benchmark", "workspace"))
REPLAYABLE_BENCHMARK_MODULE = "_".join(("replayable", "benchmark", "harness"))
REPO_MEMORY_PROFILE_HISTORY_MODULE = "_".join(("repo", "memory", "profile", "history"))
TRUSTED_HISTORY_EVIDENCE_MODULE = "_".join(("trusted", "history", "evidence"))
NEXT_RECOMMENDED_PR = "/".join(
    (
        "feature",
        "-".join(("repo", "memory", "flaky", "test", "registry", "ingestion")),
    )
)

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
            integration_points=("diagnostic_vector_engine", "trajectory_store", "patch_scorer"),
            gaps=(
                "needs structural verifier results and later semantic proof before broader mutation use",
            ),
            recommended_next_action="feed plans through PatchScorer and protected_verifier reporting",
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
            integration_points=(
                "check_intelligence",
                "safe_remediation_eligibility",
                "patch_scorer",
            ),
            gaps=(
                "PatchScorer exists but is not wired into automation yet",
                "protected_verifier exists only as read-only structural evaluation",
            ),
            recommended_next_action="keep formatting-only and unwired until stronger verification exists",
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
            role="render operator-facing PR Quality status, evidence, trajectory, runtime-proof, and trusted-history summaries",
            status="aligned",
            stages=("reporting", "trajectory", "proof", "history"),
            existing_artifacts=("pr-comment-body.md", "pr-comment-metadata.json"),
            integration_points=(
                "check_intelligence",
                "trajectory_store",
                "pr_quality_runtime_proof_artifacts",
            ),
            recommended_next_action="keep accepted-main history advisory-only and no-authority boundaries explicit",
        ),
        _component(
            module="pr_quality_runtime_proof_artifacts",
            role="summarize isolated proof, live benchmark, RepoMemory, and trusted accepted-main history evidence for PR Quality visibility",
            status="aligned",
            stages=("proof", "benchmark", "history", "reporting"),
            existing_artifacts=(
                "runtime-proof-artifacts.json",
                "runtime-proof-artifacts.md",
            ),
            integration_points=(
                "git_inventory_collector",
                "isolated_proof_runner",
                "proof_runtime_guard",
                "network_boundary",
                PR_QUALITY_LIVE_WORKSPACE_MODULE,
                "replayable_benchmark_harness",
                "repo_memory",
                TRUSTED_HISTORY_EVIDENCE_MODULE,
                "pr_quality_action_report",
            ),
            recommended_next_action="keep runtime, benchmark, memory, and accepted-main history visibility reporting-only",
        ),
        _component(
            module=PR_QUALITY_LIVE_WORKSPACE_MODULE,
            role="prepare disposable Git scenario repositories for live PR Quality benchmark evidence",
            status="aligned",
            stages=("proof", "benchmark", "reporting"),
            existing_artifacts=(
                "workspace-manifest.json",
                "workspace-manifest.md",
            ),
            integration_points=(
                REPLAYABLE_BENCHMARK_MODULE,
                "pr_quality_runtime_proof_artifacts",
            ),
            recommended_next_action="keep generated scenario repositories temporary and non-authoritative",
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
            integration_points=("trajectory_store", "trajectory_pattern_insights"),
            recommended_next_action="feed trajectory pattern insights and later RepoMemory",
        ),
        _component(
            module="trajectory_pattern_insights",
            role="detect recurring review-first and safe-fix patterns from trajectory history",
            status="aligned",
            stages=("history", "decision", "reporting"),
            existing_artifacts=("trajectory pattern insights JSON/Markdown reports",),
            integration_points=(
                "trajectory_history_report",
                "patch_scorer",
                "repo_memory",
            ),
            recommended_next_action="feed candidate patterns into patch_scorer and repo_memory without expanding automation",
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
            module="patch_scorer",
            role="score proposed patch safety before any future automation consumes it",
            status="partially_aligned",
            stages=("decision", "remediation_eligibility", "proof"),
            existing_artifacts=("patch-score.json", "patch-score.md"),
            integration_points=(
                "remediation_plan_engine",
                "trajectory_pattern_insights",
                "protected_verifier",
            ),
            gaps=(
                "read-only prototype is not wired into maintenance_autopilot",
                "structural verification does not yet prove semantic equivalence",
            ),
            recommended_next_action="feed candidates to protected_verifier without changing automation",
        ),
        _component(
            module="protected_verifier",
            role="verify PatchScorer candidate scope and captured proof results without authorizing mutation",
            status="partially_aligned",
            stages=("proof", "verifier", "reporting"),
            existing_artifacts=(
                "protected-verifier-result.json",
                "protected-verifier-result.md",
            ),
            integration_points=(
                "patch_scorer",
                "git_inventory_collector",
                "isolated_proof_runner",
                "replayable_benchmark_harness",
                "maintenance_autopilot",
            ),
            gaps=(
                "Git-derived allowlisted proof is benchmarked only for limited live scenarios",
                "structural and allowlisted command proof do not establish semantic equivalence",
                "not wired into automation",
            ),
            recommended_next_action="extend anti-cheat and isolation proof without changing automation",
        ),
        _component(
            module="git_inventory_collector",
            role="derive changed-file inventories from fixed read-only Git queries",
            status="partially_aligned",
            stages=("evidence", "proof", "verifier"),
            existing_artifacts=(
                "git-inventory.json",
                "git-inventory.md",
            ),
            integration_points=(
                "isolated_proof_runner",
                "protected_verifier",
                "replayable_benchmark_harness",
            ),
            gaps=(
                "workflow visibility uses Git-derived inventory only for a narrow allowlisted Ruff proof profile",
            ),
            recommended_next_action="keep Git-derived workflow proof read-only and narrowly scoped",
        ),
        _component(
            module="network_boundary",
            role="block proof execution when required network isolation lacks a verified runtime backend",
            status="partially_aligned",
            stages=("proof", "verifier", "reporting"),
            existing_artifacts=(
                "network-boundary.json",
                "network-boundary.md",
            ),
            integration_points=(
                "isolated_proof_runner",
                "replayable_benchmark_harness",
                "repo_memory",
            ),
            gaps=(
                "no runtime containment backend has a verified network-isolation contract",
                "the observed unshare probe is not sufficient to claim enforcement",
            ),
            recommended_next_action="register a backend only after successful containment proof",
        ),
        _component(
            module="proof_runtime_guard",
            role="classify copied-workspace writes and reserved evidence shadowing during proof execution",
            status="partially_aligned",
            stages=("proof", "verifier", "reporting"),
            existing_artifacts=("embedded runtime-guard evidence",),
            integration_points=(
                "isolated_proof_runner",
                "replayable_benchmark_harness",
                "repo_memory",
            ),
            gaps=(
                "detects copied-workspace behavior but does not prevent external filesystem writes",
                "process escape prevention remains unavailable",
            ),
            recommended_next_action="keep runtime-guard visibility reporting-only",
        ),
        _component(
            module="isolated_proof_runner",
            role="execute allowlisted proof profiles in a disposable workspace copy and capture results",
            status="partially_aligned",
            stages=("proof", "verifier", "reporting"),
            existing_artifacts=(
                "verification-evidence.json",
                "verification-evidence.md",
                "network-boundary.json",
            ),
            integration_points=(
                "git_inventory_collector",
                "network_boundary",
                "proof_runtime_guard",
                "protected_verifier",
                "replayable_benchmark_harness",
                "repo_memory",
            ),
            gaps=(
                "successful network-isolated proof execution remains unavailable",
                "external filesystem and process escape prevention remain unavailable",
            ),
            recommended_next_action="expand visibility only through read-only artifact collection",
        ),
        _component(
            module="replayable_benchmark_harness",
            role="replay fixture-backed and Git-grounded isolated-proof scenarios through safety contracts",
            status="partially_aligned",
            stages=("benchmark", "proof", "verifier", "reporting"),
            existing_artifacts=(
                "benchmark-report.json",
                "benchmark-report.md",
                "fixture scenario JSON",
                "Git-grounded isolated-proof scenario reports",
            ),
            integration_points=(
                "git_inventory_collector",
                "network_boundary",
                "proof_runtime_guard",
                "isolated_proof_runner",
                "patch_scorer",
                "protected_verifier",
                "repo_memory",
            ),
            gaps=("successful containment remains unavailable",),
            recommended_next_action="keep live benchmark evidence reporting-only until containment is proven",
        ),
        _component(
            module="repo_memory",
            role="produce local repo-specific memory profiles from trajectory and benchmark evidence",
            status="partially_aligned",
            stages=("history", "decision", "reporting"),
            existing_artifacts=(
                "repo-memory-profile.json",
                "repo-memory-profile.md",
            ),
            integration_points=(
                "trajectory_pattern_insights",
                "network_boundary",
                "proof_runtime_guard",
                "replayable_benchmark_harness",
                "protected_verifier",
                "pr_quality_runtime_proof_artifacts",
                REPO_MEMORY_PROFILE_HISTORY_MODULE,
            ),
            gaps=(
                "successful network-isolation proof is unavailable until a backend is verified",
                "flaky-test registry ingestion is not implemented",
            ),
            recommended_next_action="ingest read-only flaky-test history without expanding authority",
        ),
        _component(
            module=REPO_MEMORY_PROFILE_HISTORY_MODULE,
            role="record trusted-main RepoMemory profile snapshots through an immutable artifact history chain",
            status="aligned",
            stages=("history", "reporting"),
            existing_artifacts=(
                "repo-memory-profile-history.jsonl",
                "repo-memory-history-summary.json",
                "repo-memory-history-summary.md",
            ),
            integration_points=(
                "repo_memory",
                TRUSTED_HISTORY_EVIDENCE_MODULE,
                "RepoMemory Profile History workflow",
            ),
            recommended_next_action="keep trusted-main history immutable and advisory-only",
        ),
        _component(
            module=TRUSTED_HISTORY_EVIDENCE_MODULE,
            role="validate successful accepted-main RepoMemory history artifacts for advisory PR Quality visibility",
            status="aligned",
            stages=("evidence", "history", "reporting"),
            existing_artifacts=(
                "trusted-history-evidence.json",
                "trusted-history-evidence.md",
            ),
            integration_points=(
                REPO_MEMORY_PROFILE_HISTORY_MODULE,
                "pr_quality_runtime_proof_artifacts",
                "pr_quality_action_report",
                "PR Quality workflow",
            ),
            recommended_next_action="keep accepted-main history reporting-only and independent of merge authority",
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
        "next_recommended_pr": NEXT_RECOMMENDED_PR,
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
