# Render a read-only diagnostic-signal baseline snapshot for PR Quality.
#
# This artifact measures observed signal counts for later reviewed KPI
# aggregation. It does not infer a historical false-positive rate, change a
# PR decision, execute proof commands, apply patches, or authorize remediation.

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = ".".join(("sdetkit", "diagnostic", "signal", "snapshot", "v1"))
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "diagnostic-signal-snapshot"
SNAPSHOT_JSON = "diagnostic-signal-snapshot.json"
REPORT_MD = "diagnostic-signal-snapshot.md"
QUIET_GREEN_STATUS = "_".join(("quiet", "green", "advisory", "baseline"))
OBSERVED_STATUS = "_".join(("diagnostic", "signal", "observed"))
RATE_STATUS = "_".join(("requires", "reviewed", "history"))

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _read_json(path: Path) -> JsonObject:
    if not path.exists():
        raise ValueError(f"declared diagnostic signal snapshot input is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _boundary() -> JsonObject:
    return {
        "reporting_only": True,
        "current_pr_decision_input": False,
        "feeds_repo_memory": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _assert_non_authorizing(payload: Mapping[str, Any], *, source: str) -> None:
    boundary = _as_dict(payload.get("decision_boundary"))
    prohibited = (
        "current_pr_decision_input",
        "patch_application_allowed",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    )
    expanded = [key for key in prohibited if _bool(boundary.get(key))]
    if expanded:
        raise ValueError(f"{source} expands authority: {', '.join(expanded)}")


def build_snapshot(
    *,
    evidence_narrative: Mapping[str, Any],
    evidence_graph: Mapping[str, Any],
    diagnostic_worker_result: Mapping[str, Any],
    runtime_proof_artifacts: Mapping[str, Any],
    security_finding_diagnosis: Mapping[str, Any],
) -> JsonObject:
    _assert_non_authorizing(diagnostic_worker_result, source="diagnostic worker result")
    _assert_non_authorizing(runtime_proof_artifacts, source="runtime proof artifacts")

    quality = _as_dict(evidence_narrative.get("quality"))
    narrative_graph = _as_dict(evidence_narrative.get("graph"))
    graph_nodes = [
        _as_dict(item) for item in _as_list(evidence_graph.get("nodes")) if _as_dict(item)
    ]
    declared_graph_count = _int(narrative_graph.get("node_count"))
    if declared_graph_count != len(graph_nodes):
        raise ValueError("evidence narrative graph count does not match Evidence Graph nodes")

    worker_summary = _as_dict(diagnostic_worker_result.get("summary"))
    isolated = _as_dict(runtime_proof_artifacts.get("isolated_proof"))
    security_rows = [
        _as_dict(item)
        for item in _as_list(security_finding_diagnosis.get("diagnoses"))
        if _as_dict(item)
    ]
    current_security_count = sum(
        1 for row in security_rows if _string(row.get("freshness")).lower() == "current"
    )
    stale_security_count = sum(
        1 for row in security_rows if _string(row.get("freshness")).lower() == "stale"
    )
    primary_signal = _as_dict(evidence_narrative.get("primary_signal"))
    primary_kind = _string(primary_signal.get("kind") or "unknown")
    primary_surface = _string(primary_signal.get("surface") or "unknown")

    measurements = {
        "quality_gate_passed": _bool(quality.get("ok")),
        "primary_signal_kind": primary_kind,
        "primary_signal_surface": primary_surface,
        "review_signal_present": primary_kind == "review_signal",
        "integration_proof_signal_present": primary_kind == "integration_proof",
        "evidence_graph_node_count": len(graph_nodes),
        "evidence_graph_review_first_count": _int(narrative_graph.get("review_first_count")),
        "diagnostic_worker_diagnosis_count": _int(worker_summary.get("diagnosis_count")),
        "diagnostic_worker_review_first_count": _int(worker_summary.get("review_first_count")),
        "diagnostic_worker_safe_fix_candidate_count": _int(
            worker_summary.get("safe_fix_candidate_count")
        ),
        "runtime_guard_violation_count": _int(isolated.get("runtime_guard_violation_count")),
        "runtime_guard_passed": _bool(isolated.get("runtime_guard_passed")),
        "current_security_finding_count": current_security_count,
        "stale_security_finding_count": stale_security_count,
    }
    quiet_green = (
        measurements["quality_gate_passed"]
        and measurements["evidence_graph_node_count"] == 0
        and measurements["evidence_graph_review_first_count"] == 0
        and measurements["diagnostic_worker_diagnosis_count"] == 0
        and measurements["diagnostic_worker_review_first_count"] == 0
        and measurements["diagnostic_worker_safe_fix_candidate_count"] == 0
        and measurements["runtime_guard_passed"]
        and measurements["runtime_guard_violation_count"] == 0
        and measurements["current_security_finding_count"] == 0
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": QUIET_GREEN_STATUS if quiet_green else OBSERVED_STATUS,
        "snapshot_type": "current_pr_reporting_only",
        "quiet_green_advisory_baseline": quiet_green,
        "measurements": measurements,
        "kpi_readiness": {
            "advisor_false_positive_rate_status": RATE_STATUS,
            "reason": (
                "This current-PR snapshot records signal counts only; a false-positive "
                "rate requires reviewed labels aggregated through trusted history."
            ),
            "reviewed_false_positive_count": None,
            "reviewed_observation_count": None,
        },
        "decision_boundary": _boundary(),
    }


def render_markdown(snapshot: Mapping[str, Any]) -> str:
    measurements = _as_dict(snapshot.get("measurements"))
    readiness = _as_dict(snapshot.get("kpi_readiness"))
    boundary = _as_dict(snapshot.get("decision_boundary"))
    return "\n".join(
        [
            "## Diagnostic signal KPI snapshot",
            "",
            "- Evidence type: `current_pr_reporting_only_snapshot`",
            f"- Status: `{_string(snapshot.get('status'))}`",
            (
                "- Quiet green advisory baseline: "
                f"`{str(_bool(snapshot.get('quiet_green_advisory_baseline'))).lower()}`"
            ),
            f"- Quality gate passed: `{str(_bool(measurements.get('quality_gate_passed'))).lower()}`",
            f"- Primary narrative signal kind: `{_string(measurements.get('primary_signal_kind'))}`",
            (
                "- Review signal present: "
                f"`{str(_bool(measurements.get('review_signal_present'))).lower()}`"
            ),
            (
                "- Integration proof signal present: "
                f"`{str(_bool(measurements.get('integration_proof_signal_present'))).lower()}`"
            ),
            f"- Evidence Graph nodes: `{_int(measurements.get('evidence_graph_node_count'))}`",
            (
                "- Evidence Graph review-first nodes: "
                f"`{_int(measurements.get('evidence_graph_review_first_count'))}`"
            ),
            (
                "- DiagnosticWorker diagnoses: "
                f"`{_int(measurements.get('diagnostic_worker_diagnosis_count'))}`"
            ),
            (
                "- DiagnosticWorker review-first diagnoses: "
                f"`{_int(measurements.get('diagnostic_worker_review_first_count'))}`"
            ),
            (
                "- DiagnosticWorker safe-fix candidates: "
                f"`{_int(measurements.get('diagnostic_worker_safe_fix_candidate_count'))}`"
            ),
            (
                "- Runtime guard violations: "
                f"`{_int(measurements.get('runtime_guard_violation_count'))}`"
            ),
            (
                "- Current security findings: "
                f"`{_int(measurements.get('current_security_finding_count'))}`"
            ),
            (
                "- Stale security findings retained as context: "
                f"`{_int(measurements.get('stale_security_finding_count'))}`"
            ),
            (
                "- Advisor false-positive rate status: "
                f"`{_string(readiness.get('advisor_false_positive_rate_status'))}`"
            ),
            "- Interpretation: this snapshot records live diagnostic-signal counts for later reviewed KPI aggregation; it does not label observations as false positives by itself.",
            "",
            "### Boundary",
            "",
            f"- Reporting only: `{str(_bool(boundary.get('reporting_only'))).lower()}`",
            (
                "- Current PR decision input: "
                f"`{str(_bool(boundary.get('current_pr_decision_input'))).lower()}`"
            ),
            f"- Feeds RepoMemory: `{str(_bool(boundary.get('feeds_repo_memory'))).lower()}`",
            (
                "- Proof commands executed: "
                f"`{str(_bool(boundary.get('proof_commands_executed'))).lower()}`"
            ),
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
        ]
    )


def write_snapshot(snapshot: Mapping[str, Any], *, out_dir: Path) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SNAPSHOT_JSON
    markdown_path = out_dir / REPORT_MD
    json_path.write_text(
        json.dumps(dict(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(snapshot), encoding="utf-8")
    return {
        "diagnostic_signal_snapshot_json": json_path.as_posix(),
        "diagnostic_signal_snapshot_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.diagnostic_signal_snapshot")
    parser.add_argument("--evidence-narrative", type=Path, required=True)
    parser.add_argument("--evidence-graph", type=Path, required=True)
    parser.add_argument("--diagnostic-worker-result", type=Path, required=True)
    parser.add_argument("--runtime-proof-artifacts", type=Path, required=True)
    parser.add_argument("--security-finding-diagnosis", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = build_snapshot(
        evidence_narrative=_read_json(args.evidence_narrative),
        evidence_graph=_read_json(args.evidence_graph),
        diagnostic_worker_result=_read_json(args.diagnostic_worker_result),
        runtime_proof_artifacts=_read_json(args.runtime_proof_artifacts),
        security_finding_diagnosis=_read_json(args.security_finding_diagnosis),
    )
    artifacts = write_snapshot(snapshot, out_dir=args.out_dir)
    output = {"snapshot": snapshot, "artifacts": artifacts}
    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(render_markdown(snapshot), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
