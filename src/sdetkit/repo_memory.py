from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.repo_memory.v1"
DEFAULT_OUT_DIR = Path("build") / "repo-memory"
PROFILE_JSON = "repo-memory-profile.json"
PROFILE_MD = "repo-memory-profile.md"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _decision_status(payload: Mapping[str, Any]) -> str:
    return _string(_as_dict(payload.get("decision")).get("status"))


def _benchmark_contract_proven(benchmark_report: Mapping[str, Any]) -> bool:
    required = _as_dict(benchmark_report.get("required_contract"))
    boundary = _as_dict(benchmark_report.get("safety_boundary"))
    return (
        _string(benchmark_report.get("status")) == "passed"
        and _bool(required.get("all_required_present"))
        and _bool(required.get("all_required_passed"))
        and _bool(boundary.get("preserved"))
        and _int(boundary.get("automation_allowed_count")) == 0
        and _int(boundary.get("merge_authorized_count")) == 0
        and _int(boundary.get("semantic_equivalence_claimed_count")) == 0
    )


def _proof_commands(benchmark_report: Mapping[str, Any]) -> list[str]:
    commands: set[str] = set()
    for scenario in _as_list(benchmark_report.get("scenarios")):
        patch_score = _as_dict(_as_dict(scenario).get("patch_score"))
        for command in _as_list(patch_score.get("proof_requirements")):
            rendered = _string(command)
            if rendered:
                commands.add(rendered)
    return sorted(commands)


def _oracle_supports_pattern(
    *,
    benchmark_report: Mapping[str, Any],
    failure_class: str,
    action: str,
) -> bool:
    if not _benchmark_contract_proven(benchmark_report):
        return False

    for scenario in _as_list(benchmark_report.get("scenarios")):
        row = _as_dict(scenario)
        if _string(row.get("scenario_type")) != "oracle_pass" or not _bool(row.get("passed")):
            continue

        patch_score = _as_dict(row.get("patch_score"))
        verifier = _as_dict(row.get("protected_verifier_result"))
        if (
            _string(patch_score.get("classification")) == failure_class
            and _string(patch_score.get("strategy")) == action
            and _decision_status(patch_score) == "candidate_for_protected_verification"
            and _decision_status(verifier) == "structurally_verified_candidate"
        ):
            return True

    return False


def _safe_fix_history(
    *,
    pattern_insights: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(pattern_insights.get("recurring_safe_fix_patterns")):
        pattern = _as_dict(item)
        failure_class = _string(pattern.get("failure_class") or "unknown")
        action = _string(pattern.get("action") or "unknown")
        supported = _oracle_supports_pattern(
            benchmark_report=benchmark_report,
            failure_class=failure_class,
            action=action,
        )
        records.append(
            {
                "failure_class": failure_class,
                "action": action,
                "trajectory_count": _int(pattern.get("count")),
                "benchmark_supported": supported,
                "proof_state": (
                    "benchmark_supported_candidate" if supported else "trajectory_observed_only"
                ),
                "automation_allowed": False,
                "reason": (
                    "A repeated trajectory pattern has matching passing oracle evidence, "
                    "but automation remains disabled."
                    if supported
                    else "Trajectory repetition exists without matching benchmark proof."
                ),
            }
        )
    return records


def _review_first_patterns(pattern_insights: Mapping[str, Any]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(pattern_insights.get("recurring_review_first_surfaces")):
        pattern = _as_dict(item)
        records.append(
            {
                "pattern_kind": "review_first_surface",
                "surface": _string(pattern.get("value") or "unknown"),
                "trajectory_count": _int(pattern.get("count")),
                "decision": "review_first",
                "automation_allowed": False,
            }
        )
    return records


def _benchmark_rejections(benchmark_report: Mapping[str, Any]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for item in _as_list(benchmark_report.get("scenarios")):
        scenario = _as_dict(item)
        scenario_type = _string(scenario.get("scenario_type"))
        if scenario_type not in {"nop_fail", "unsafe_patch_fail"}:
            continue
        if not _bool(scenario.get("passed")):
            continue

        records.append(
            {
                "pattern_kind": "benchmark_rejection",
                "scenario_id": _string(scenario.get("scenario_id")),
                "scenario_type": scenario_type,
                "patch_score_status": _decision_status(_as_dict(scenario.get("patch_score"))),
                "verifier_status": _decision_status(
                    _as_dict(scenario.get("protected_verifier_result"))
                ),
                "decision": "blocked_review_first",
                "automation_allowed": False,
            }
        )
    return records


def _escalation_rules() -> list[JsonObject]:
    return [
        {
            "rule_id": "current_security_evidence_review_first",
            "when": "a current security review or code-scanning finding exists",
            "decision": "review_first",
            "automation_allowed": False,
        },
        {
            "rule_id": "unsupported_safe_pattern_advisory_only",
            "when": "a repeated safe-fix pattern lacks passing oracle benchmark evidence",
            "decision": "keep_advisory",
            "automation_allowed": False,
        },
        {
            "rule_id": "structural_proof_not_semantic_equivalence",
            "when": "protected structural verification passes without isolated runtime proof",
            "decision": "do_not_authorize_automation",
            "automation_allowed": False,
        },
    ]


def build_repo_memory_profile(
    *,
    pattern_insights: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
) -> JsonObject:
    benchmark_proven = _benchmark_contract_proven(benchmark_report)
    safe_fix_history = _safe_fix_history(
        pattern_insights=pattern_insights,
        benchmark_report=benchmark_report,
    )
    review_first = _review_first_patterns(pattern_insights)
    benchmark_rejections = _benchmark_rejections(benchmark_report)
    supported_candidates = [
        item for item in safe_fix_history if _bool(item.get("benchmark_supported"))
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "profile_status": (
            "benchmark_supported_memory" if benchmark_proven else "observation_only"
        ),
        "memory_mode": "read_only_profile",
        "inputs": {
            "trajectory_pattern_schema": _string(pattern_insights.get("schema_version")),
            "trajectory_record_count": _int(pattern_insights.get("record_count")),
            "benchmark_schema": _string(benchmark_report.get("schema_version")),
            "benchmark_status": _string(benchmark_report.get("status")),
            "benchmark_contract_proven": benchmark_proven,
        },
        "command_profile": {
            "source": "replayable_benchmark_harness",
            "observed_proof_commands": _proof_commands(benchmark_report),
            "commands_executed_by_repo_memory": False,
            "note": (
                "Commands are stored from benchmark evidence only; "
                "RepoMemory does not execute proof commands."
            ),
        },
        "failure_patterns": {
            "review_first": review_first,
            "benchmark_rejections": benchmark_rejections,
        },
        "safe_fix_history": safe_fix_history,
        "known_safe_candidate_count": len(supported_candidates),
        "flaky_test_registry": {
            "collection_status": "not_collected",
            "entries": [],
            "note": "No flaky-test evidence source is connected to RepoMemory yet.",
        },
        "escalation_rules": _escalation_rules(),
        "unproven_boundaries": [
            "semantic equivalence",
            "isolated proof-command execution",
            "anti-cheat runtime validation",
            "broader remediation classes beyond formatting-only candidates",
        ],
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": (
                "RepoMemory records observed and benchmark-supported patterns; "
                "it does not authorize remediation."
            ),
        },
        "recommended_next_action": (
            "Add isolated proof-command execution and anti-cheat checks "
            "before any automation wiring."
        ),
    }


def render_markdown(profile: Mapping[str, Any]) -> str:
    inputs = _as_dict(profile.get("inputs"))
    commands = _as_dict(profile.get("command_profile"))
    failure_patterns = _as_dict(profile.get("failure_patterns"))
    flaky = _as_dict(profile.get("flaky_test_registry"))
    boundary = _as_dict(profile.get("decision_boundary"))

    lines = [
        "# RepoMemory profile",
        "",
        f"- Schema: `{_string(profile.get('schema_version'))}`",
        f"- Status: `{_string(profile.get('profile_status'))}`",
        f"- Mode: `{_string(profile.get('memory_mode'))}`",
        f"- Trajectory records observed: `{_int(inputs.get('trajectory_record_count'))}`",
        (
            "- Benchmark contract proven: "
            f"`{str(_bool(inputs.get('benchmark_contract_proven'))).lower()}`"
        ),
        f"- Known safe candidates: `{_int(profile.get('known_safe_candidate_count'))}`",
        "",
        "## Command profile",
        "",
    ]

    proof_commands = [_string(item) for item in _as_list(commands.get("observed_proof_commands"))]
    if proof_commands:
        lines.extend(f"- `{command}`" for command in proof_commands)
    else:
        lines.append("- none observed")
    lines.append("- RepoMemory executes commands: `false`")

    lines.extend(["", "## Safe-fix history", ""])
    safe_history = [_as_dict(item) for item in _as_list(profile.get("safe_fix_history"))]
    if safe_history:
        for item in safe_history:
            lines.append(
                f"- class=`{_string(item.get('failure_class'))}`, "
                f"action=`{_string(item.get('action'))}`, "
                f"trajectory_count=`{_int(item.get('trajectory_count'))}`, "
                f"proof_state=`{_string(item.get('proof_state'))}`, "
                "automation_allowed=`false`"
            )
    else:
        lines.append("- none observed")

    lines.extend(["", "## Review-first failure patterns", ""])
    review_first = [_as_dict(item) for item in _as_list(failure_patterns.get("review_first"))]
    rejections = [_as_dict(item) for item in _as_list(failure_patterns.get("benchmark_rejections"))]
    if review_first:
        for item in review_first:
            lines.append(
                f"- recurring surface=`{_string(item.get('surface'))}`, "
                f"trajectory_count=`{_int(item.get('trajectory_count'))}`"
            )
    if rejections:
        for item in rejections:
            lines.append(
                f"- benchmark scenario=`{_string(item.get('scenario_id'))}`, "
                f"type=`{_string(item.get('scenario_type'))}`, "
                "decision=`blocked_review_first`"
            )
    if not review_first and not rejections:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Flaky test registry",
            "",
            f"- Collection status: `{_string(flaky.get('collection_status'))}`",
            f"- Entries: `{len(_as_list(flaky.get('entries')))}`",
            "",
            "## Escalation rules",
            "",
        ]
    )
    for rule in _as_list(profile.get("escalation_rules")):
        item = _as_dict(rule)
        lines.append(
            f"- `{_string(item.get('rule_id'))}`: "
            f"decision=`{_string(item.get('decision'))}`, automation_allowed=`false`"
        )

    lines.extend(["", "## Unproven boundaries", ""])
    for item in _as_list(profile.get("unproven_boundaries")):
        lines.append(f"- {_string(item)}")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            f"- Next: {_string(profile.get('recommended_next_action'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_profile(profile: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / PROFILE_JSON
    markdown_path = out_dir / PROFILE_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(profile), encoding="utf-8")
    return {
        "repo_memory_profile_json": json_path.as_posix(),
        "repo_memory_profile_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.repo_memory")
    parser.add_argument("--pattern-insights", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        profile = build_repo_memory_profile(
            pattern_insights=_read_json(args.pattern_insights),
            benchmark_report=_read_json(args.benchmark_report),
        )
        artifacts = write_profile(profile, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "profile_status": profile["profile_status"],
                    "artifacts": artifacts,
                    "known_safe_candidate_count": profile["known_safe_candidate_count"],
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
