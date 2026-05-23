from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_quality_runtime_proof_artifacts.v1"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "runtime-proof" / "summary"
SUMMARY_JSON = "runtime-proof-artifacts.json"
SUMMARY_MD = "runtime-proof-artifacts.md"

COLLECTED = "collected"
NOT_COLLECTED = "_".join(("not", "collected"))

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _isolated_proof_summary(evidence: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(evidence)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    proof_summary = _as_dict(payload.get("proof_summary"))
    runtime_guard = _as_dict(payload.get("runtime_guard"))
    network_boundary = _as_dict(payload.get("network_boundary"))
    isolation = _as_dict(payload.get("isolation"))
    decision_boundary = _as_dict(payload.get("decision_boundary"))

    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "git_inventory_verified": _bool(decision_boundary.get("git_inventory_verified")),
        "runtime_guard_checked": _bool(runtime_guard.get("checked")),
        "runtime_guard_passed": _bool(runtime_guard.get("passed")),
        "runtime_guard_violation_count": _int(runtime_guard.get("violation_count")),
        "runtime_guard_status_counts": _as_dict(runtime_guard.get("status_counts")),
        "network_boundary_status": _string(
            network_boundary.get("status") or isolation.get("network_boundary_status")
        ),
        "network_isolation_required": _bool(isolation.get("network_isolation_required")),
        "network_isolation_enforced": _bool(isolation.get("network_isolation_enforced")),
        "proof_execution_blocked": _bool(isolation.get("proof_execution_blocked")),
        "profiles_requested": _int(proof_summary.get("requested_count")),
        "profiles_executed": _int(proof_summary.get("executed_count")),
        "profiles_blocked": _int(proof_summary.get("blocked_count")),
        "profiles_passed": _int(proof_summary.get("passed_count")),
        "profiles_failed": _int(proof_summary.get("failed_count")),
    }


def _live_benchmark_summary(report: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(report)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    live = _as_dict(payload.get("live_evidence"))
    boundary = _as_dict(payload.get("safety_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("status") or "unknown"),
        "report_mode": _string(payload.get("report_mode") or "unknown"),
        "scenario_count": _int(payload.get("scenario_count")),
        "passed_count": _int(payload.get("passed_count")),
        "failed_count": _int(payload.get("failed_count")),
        "git_inventory_verified_count": _int(live.get("git_inventory_verified_count")),
        "expected_failed_evidence_count": _int(live.get("expected_failed_evidence_count")),
        "network_boundary_blocked_count": _int(live.get("network_boundary_blocked_count")),
        "anti_cheat_rejection_count": _int(live.get("anti_cheat_rejection_count")),
        "network_isolation_enforced_count": _int(live.get("network_isolation_enforced_count")),
        "automation_allowed_count": _int(boundary.get("automation_allowed_count")),
        "merge_authorized_count": _int(boundary.get("merge_authorized_count")),
        "semantic_equivalence_claimed_count": _int(
            boundary.get("semantic_equivalence_claimed_count")
        ),
        "boundary_preserved": _bool(boundary.get("preserved")),
    }


def _repo_memory_summary(profile: Mapping[str, Any]) -> JsonObject:
    payload = _as_dict(profile)
    if not payload:
        return {
            "collection_status": NOT_COLLECTED,
            "status": NOT_COLLECTED,
        }

    provenance = _as_dict(payload.get("proof_provenance"))
    boundary = _as_dict(payload.get("decision_boundary"))
    return {
        "collection_status": COLLECTED,
        "status": _string(payload.get("profile_status") or "unknown"),
        "live_contract_proven": _bool(provenance.get("live_contract_proven")),
        "known_safe_candidate_count": _int(payload.get("known_safe_candidate_count")),
        "live_safe_candidate_count": _int(payload.get("live_safe_candidate_count")),
        "git_verified_scenario_count": _int(provenance.get("git_verified_scenario_count")),
        "expected_failed_scenario_count": _int(provenance.get("expected_failed_scenario_count")),
        "network_boundary_blocked_scenario_count": _int(
            provenance.get("network_boundary_blocked_scenario_count")
        ),
        "anti_cheat_rejection_scenario_count": _int(
            provenance.get("anti_cheat_rejection_scenario_count")
        ),
        "automation_allowed": _bool(boundary.get("automation_allowed")),
        "merge_authorized": _bool(boundary.get("merge_authorized")),
        "semantic_equivalence_proven": _bool(boundary.get("semantic_equivalence_proven")),
    }


def build_runtime_proof_artifacts(
    *,
    isolated_proof: Mapping[str, Any] | None = None,
    live_benchmark_report: Mapping[str, Any] | None = None,
    repo_memory_profile: Mapping[str, Any] | None = None,
) -> JsonObject:
    isolated = _isolated_proof_summary(isolated_proof or {})
    live_benchmark = _live_benchmark_summary(live_benchmark_report or {})
    repo_memory = _repo_memory_summary(repo_memory_profile or {})

    collected_components = [
        name
        for name, component in (
            ("isolated_proof", isolated),
            ("live_benchmark", live_benchmark),
            ("repo_memory", repo_memory),
        )
        if component["collection_status"] == COLLECTED
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": COLLECTED if collected_components else NOT_COLLECTED,
        "collected_components": collected_components,
        "isolated_proof": isolated,
        "live_benchmark": live_benchmark,
        "repo_memory": repo_memory,
        "decision_boundary": {
            "reporting_only": True,
            "proof_commands_executed_by_renderer": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    isolated = _as_dict(summary.get("isolated_proof"))
    benchmark = _as_dict(summary.get("live_benchmark"))
    memory = _as_dict(summary.get("repo_memory"))
    boundary = _as_dict(summary.get("decision_boundary"))

    lines = [
        "# PR Quality runtime proof artifacts",
        "",
        f"- Status: `{_string(summary.get('status'))}`",
        "",
        "## Isolated runtime proof",
        "",
        f"- Collection status: `{_string(isolated.get('collection_status'))}`",
        f"- Status: `{_string(isolated.get('status'))}`",
    ]

    if isolated.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (
                    "- Git inventory verified: "
                    f"`{str(_bool(isolated.get('git_inventory_verified'))).lower()}`"
                ),
                (
                    "- Runtime guard checked: "
                    f"`{str(_bool(isolated.get('runtime_guard_checked'))).lower()}`"
                ),
                (
                    "- Runtime guard passed: "
                    f"`{str(_bool(isolated.get('runtime_guard_passed'))).lower()}`"
                ),
                (
                    "- Runtime guard violations: "
                    f"`{_int(isolated.get('runtime_guard_violation_count'))}`"
                ),
                (
                    "- Network boundary status: "
                    f"`{_string(isolated.get('network_boundary_status'))}`"
                ),
                (
                    "- Network isolation enforced: "
                    f"`{str(_bool(isolated.get('network_isolation_enforced'))).lower()}`"
                ),
                f"- Profiles executed: `{_int(isolated.get('profiles_executed'))}`",
                f"- Profiles blocked: `{_int(isolated.get('profiles_blocked'))}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Live benchmark evidence",
            "",
            f"- Collection status: `{_string(benchmark.get('collection_status'))}`",
            f"- Status: `{_string(benchmark.get('status'))}`",
        ]
    )
    if benchmark.get("collection_status") == COLLECTED:
        lines.extend(
            [
                f"- Report mode: `{_string(benchmark.get('report_mode'))}`",
                f"- Scenarios: `{_int(benchmark.get('scenario_count'))}`",
                f"- Passed: `{_int(benchmark.get('passed_count'))}`",
                (
                    "- Git inventory verified scenarios: "
                    f"`{_int(benchmark.get('git_inventory_verified_count'))}`"
                ),
                (
                    "- Expected failed-evidence scenarios: "
                    f"`{_int(benchmark.get('expected_failed_evidence_count'))}`"
                ),
                (
                    "- Network boundary blocked scenarios: "
                    f"`{_int(benchmark.get('network_boundary_blocked_count'))}`"
                ),
                (
                    "- Anti-cheat rejection scenarios: "
                    f"`{_int(benchmark.get('anti_cheat_rejection_count'))}`"
                ),
                (
                    "- Network isolation enforced scenarios: "
                    f"`{_int(benchmark.get('network_isolation_enforced_count'))}`"
                ),
                (
                    "- Boundary preserved: "
                    f"`{str(_bool(benchmark.get('boundary_preserved'))).lower()}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## RepoMemory evidence",
            "",
            f"- Collection status: `{_string(memory.get('collection_status'))}`",
            f"- Status: `{_string(memory.get('status'))}`",
        ]
    )
    if memory.get("collection_status") == COLLECTED:
        lines.extend(
            [
                (
                    "- Live contract proven: "
                    f"`{str(_bool(memory.get('live_contract_proven'))).lower()}`"
                ),
                (f"- Known safe candidates: `{_int(memory.get('known_safe_candidate_count'))}`"),
                (f"- Live safe candidates: `{_int(memory.get('live_safe_candidate_count'))}`"),
                (
                    "- Git inventory verified scenarios: "
                    f"`{_int(memory.get('git_verified_scenario_count'))}`"
                ),
                (
                    "- Anti-cheat rejection scenarios: "
                    f"`{_int(memory.get('anti_cheat_rejection_scenario_count'))}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "- Proof commands executed by renderer: "
                f"`{str(_bool(boundary.get('proof_commands_executed_by_renderer'))).lower()}`"
            ),
            (f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`"),
            (f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`"),
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(summary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "runtime_proof_artifacts_json": json_path.as_posix(),
        "runtime_proof_artifacts_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_runtime_proof_artifacts")
    parser.add_argument("--isolated-proof", type=Path)
    parser.add_argument("--live-benchmark-report", type=Path)
    parser.add_argument("--repo-memory-profile", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_runtime_proof_artifacts(
        isolated_proof=_read_json(args.isolated_proof),
        live_benchmark_report=_read_json(args.live_benchmark_report),
        repo_memory_profile=_read_json(args.repo_memory_profile),
    )
    artifacts = write_summary(summary, out_dir=args.out_dir)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "collected_components": summary["collected_components"],
                    "isolated_proof_status": summary["isolated_proof"]["status"],
                    "live_benchmark_status": summary["live_benchmark"]["status"],
                    "repo_memory_status": summary["repo_memory"]["status"],
                    "anti_cheat_rejection_count": summary["live_benchmark"].get(
                        "anti_cheat_rejection_count", 0
                    ),
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
