from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.patch_scorer import score_patch
from sdetkit.protected_verifier import verify_candidate

SCHEMA_VERSION = "sdetkit.replayable_benchmark_harness.v1"
DEFAULT_OUT_DIR = Path("build") / "replayable-benchmark-harness"
REPORT_JSON = "benchmark-report.json"
REPORT_MD = "benchmark-report.md"

SCENARIO_TYPES = {
    "nop_fail",
    "oracle_pass",
    "unsafe_patch_fail",
}
REQUIRED_SCENARIO_TYPES = (
    "nop_fail",
    "oracle_pass",
    "unsafe_patch_fail",
)

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


def _read_json_object(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def load_scenarios(paths: list[Path]) -> list[JsonObject]:
    scenarios: list[JsonObject] = []
    identifiers: set[str] = set()

    for path in paths:
        scenario = _read_json_object(path)
        scenario_id = _string(scenario.get("scenario_id"))
        if not scenario_id:
            msg = f"scenario_id is required in {path}"
            raise ValueError(msg)
        if scenario_id in identifiers:
            msg = f"duplicate scenario_id: {scenario_id}"
            raise ValueError(msg)

        scenario_type = _string(scenario.get("scenario_type"))
        if scenario_type not in SCENARIO_TYPES:
            msg = f"unsupported scenario_type for {scenario_id}: {scenario_type}"
            raise ValueError(msg)

        identifiers.add(scenario_id)
        scenarios.append(scenario)

    return scenarios


def _decision_status(payload: Mapping[str, Any]) -> str:
    return _string(_as_dict(payload.get("decision")).get("status"))


def _check(
    *,
    name: str,
    passed: bool,
    expected: Any,
    actual: Any,
) -> JsonObject:
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def evaluate_scenario(scenario: Mapping[str, Any]) -> JsonObject:
    scenario_id = _string(scenario.get("scenario_id"))
    scenario_type = _string(scenario.get("scenario_type"))
    if not scenario_id:
        raise ValueError("scenario_id is required")
    if scenario_type not in SCENARIO_TYPES:
        msg = f"unsupported scenario_type for {scenario_id}: {scenario_type}"
        raise ValueError(msg)

    remediation_plan = _as_dict(scenario.get("remediation_plan"))
    proposed_patch = _as_dict(scenario.get("proposed_patch"))
    pattern_insights = _as_dict(scenario.get("pattern_insights"))
    verification_evidence = _as_dict(scenario.get("verification_evidence"))
    expected = _as_dict(scenario.get("expected"))

    if not remediation_plan or not proposed_patch or not verification_evidence:
        msg = (
            f"scenario {scenario_id} must provide remediation_plan, "
            "proposed_patch, and verification_evidence"
        )
        raise ValueError(msg)

    patch_score = score_patch(
        remediation_plan=remediation_plan,
        proposed_patch=proposed_patch,
        pattern_insights=pattern_insights,
        diagnosis_id=_string(scenario.get("diagnosis_id")),
        minimum_score=_int(scenario.get("minimum_score"), default=80),
    )
    verifier_result = verify_candidate(
        patch_score=patch_score,
        verification_evidence=verification_evidence,
    )

    patch_status = _decision_status(patch_score)
    verifier_status = _decision_status(verifier_result)
    scorer_decision = _as_dict(patch_score.get("decision"))
    verifier_decision = _as_dict(verifier_result.get("decision"))

    expected_patch_status = _string(expected.get("patch_score_status"))
    expected_verifier_status = _string(expected.get("verifier_status"))
    if not expected_patch_status or not expected_verifier_status:
        msg = f"scenario {scenario_id} must declare expected decision statuses"
        raise ValueError(msg)

    checks = [
        _check(
            name="patch_score_status",
            passed=patch_status == expected_patch_status,
            expected=expected_patch_status,
            actual=patch_status,
        ),
        _check(
            name="protected_verifier_status",
            passed=verifier_status == expected_verifier_status,
            expected=expected_verifier_status,
            actual=verifier_status,
        ),
        _check(
            name="patch_score_automation_boundary",
            passed=not _bool(scorer_decision.get("automation_allowed")),
            expected=False,
            actual=_bool(scorer_decision.get("automation_allowed")),
        ),
        _check(
            name="protected_verifier_automation_boundary",
            passed=not _bool(verifier_decision.get("automation_allowed")),
            expected=False,
            actual=_bool(verifier_decision.get("automation_allowed")),
        ),
        _check(
            name="protected_verifier_merge_boundary",
            passed=not _bool(verifier_decision.get("merge_authorized")),
            expected=False,
            actual=_bool(verifier_decision.get("merge_authorized")),
        ),
        _check(
            name="semantic_equivalence_boundary",
            passed=not _bool(verifier_decision.get("semantic_equivalence_proven")),
            expected=False,
            actual=_bool(verifier_decision.get("semantic_equivalence_proven")),
        ),
    ]

    if scenario_type == "oracle_pass":
        checks.extend(
            [
                _check(
                    name="oracle_patch_candidate",
                    passed=patch_status == "candidate_for_protected_verification",
                    expected="candidate_for_protected_verification",
                    actual=patch_status,
                ),
                _check(
                    name="oracle_structural_verification",
                    passed=verifier_status == "structurally_verified_candidate"
                    and _bool(verifier_decision.get("structural_verification_passed")),
                    expected=True,
                    actual=_bool(verifier_decision.get("structural_verification_passed")),
                ),
            ]
        )
    else:
        checks.extend(
            [
                _check(
                    name="unsafe_or_nop_patch_rejected",
                    passed=patch_status == "blocked_review_first",
                    expected="blocked_review_first",
                    actual=patch_status,
                ),
                _check(
                    name="unsafe_or_nop_verification_rejected",
                    passed=verifier_status == "blocked_review_first",
                    expected="blocked_review_first",
                    actual=verifier_status,
                ),
            ]
        )

    passed = all(_bool(item.get("passed")) for item in checks)
    return {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "description": _string(scenario.get("description")),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "attempt_scored": True,
        "attempt_score": _int(patch_score.get("score")),
        "checks": checks,
        "patch_score": patch_score,
        "protected_verifier_result": verifier_result,
    }


def _type_rate(results: list[JsonObject], scenario_type: str) -> float:
    matching = [item for item in results if item.get("scenario_type") == scenario_type]
    if not matching:
        return 0.0
    passing = sum(1 for item in matching if item.get("passed") is True)
    return round(passing / len(matching), 4)


def build_benchmark_report(scenarios: list[Mapping[str, Any]]) -> JsonObject:
    results = [evaluate_scenario(scenario) for scenario in scenarios]
    type_counts = Counter(_string(item.get("scenario_type")) for item in results)
    required_present = all(type_counts.get(item, 0) >= 1 for item in REQUIRED_SCENARIO_TYPES)
    required_passed = all(
        any(
            result.get("scenario_type") == scenario_type and result.get("passed") is True
            for result in results
        )
        for scenario_type in REQUIRED_SCENARIO_TYPES
    )

    automation_allowed_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("patch_score")).get("decision")).get("automation_allowed")
        )
        or _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "automation_allowed"
            )
        )
    )
    merge_authorized_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "merge_authorized"
            )
        )
    )
    semantic_equivalence_claimed_count = sum(
        1
        for result in results
        if _bool(
            _as_dict(_as_dict(result.get("protected_verifier_result")).get("decision")).get(
                "semantic_equivalence_proven"
            )
        )
    )

    passed_count = sum(1 for item in results if item.get("passed") is True)
    boundary_preserved = (
        automation_allowed_count == 0
        and merge_authorized_count == 0
        and semantic_equivalence_claimed_count == 0
    )
    passed = (
        bool(results)
        and passed_count == len(results)
        and required_present
        and required_passed
        and boundary_preserved
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "scenario_type_counts": dict(sorted(type_counts.items())),
        "required_contract": {
            "required_scenario_types": list(REQUIRED_SCENARIO_TYPES),
            "all_required_present": required_present,
            "all_required_passed": required_passed,
            "nop_fail_rate": _type_rate(results, "nop_fail"),
            "oracle_pass_rate": _type_rate(results, "oracle_pass"),
            "unsafe_patch_rejection_rate": _type_rate(results, "unsafe_patch_fail"),
        },
        "safety_boundary": {
            "execution_model": "read_only_in_process_fixture_evaluation",
            "automation_allowed_count": automation_allowed_count,
            "merge_authorized_count": merge_authorized_count,
            "semantic_equivalence_claimed_count": semantic_equivalence_claimed_count,
            "preserved": boundary_preserved,
        },
        "attempt_scored_count": sum(1 for item in results if item.get("attempt_scored") is True),
        "scenarios": results,
        "next_boundary": (
            "Add isolated execution and anti-cheat runtime checks before any automation wiring."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    required = _as_dict(report.get("required_contract"))
    boundary = _as_dict(report.get("safety_boundary"))
    scenarios = [_as_dict(item) for item in _as_list(report.get("scenarios"))]

    lines = [
        "# Replayable Benchmark Harness report",
        "",
        f"- Status: `{_string(report.get('status'))}`",
        f"- Scenarios: `{_int(report.get('scenario_count'))}`",
        f"- Passed: `{_int(report.get('passed_count'))}`",
        f"- Failed: `{_int(report.get('failed_count'))}`",
        f"- Attempts scored: `{_int(report.get('attempt_scored_count'))}`",
        "",
        "## Required benchmark contract",
        "",
        f"- All required scenarios present: `{str(_bool(required.get('all_required_present'))).lower()}`",
        f"- All required scenarios passed: `{str(_bool(required.get('all_required_passed'))).lower()}`",
        f"- NOP fail rate: `{float(required.get('nop_fail_rate', 0.0) or 0.0):.4f}`",
        f"- Oracle pass rate: `{float(required.get('oracle_pass_rate', 0.0) or 0.0):.4f}`",
        (
            "- Unsafe patch rejection rate: "
            f"`{float(required.get('unsafe_patch_rejection_rate', 0.0) or 0.0):.4f}`"
        ),
        "",
        "## Safety boundary",
        "",
        f"- Execution model: `{_string(boundary.get('execution_model'))}`",
        f"- Automation allowed count: `{_int(boundary.get('automation_allowed_count'))}`",
        f"- Merge authorized count: `{_int(boundary.get('merge_authorized_count'))}`",
        (
            "- Semantic equivalence claimed count: "
            f"`{_int(boundary.get('semantic_equivalence_claimed_count'))}`"
        ),
        f"- Boundary preserved: `{str(_bool(boundary.get('preserved'))).lower()}`",
        "",
        "## Scenario results",
        "",
    ]

    for scenario in scenarios:
        lines.append(
            f"- `{_string(scenario.get('scenario_id'))}` "
            f"({_string(scenario.get('scenario_type'))}): "
            f"`{_string(scenario.get('status'))}`, "
            f"attempt_score=`{_int(scenario.get('attempt_score'))}`"
        )

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This harness replays deterministic fixture evidence through PatchScorer and ProtectedVerifier.",
            "- It does not apply patches or execute proof commands.",
            "- It does not authorize automation or merge.",
            f"- Next: {_string(report.get('next_boundary'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / REPORT_JSON
    markdown_path = out_dir / REPORT_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {
        "benchmark_report_json": json_path.as_posix(),
        "benchmark_report_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.replayable_benchmark_harness")
    parser.add_argument(
        "--scenario",
        type=Path,
        action="append",
        required=True,
        help="Fixture-backed benchmark scenario JSON. May be supplied more than once.",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        report = build_benchmark_report(load_scenarios(args.scenario))
        artifacts = write_report(report, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "artifacts": artifacts,
                    "scenario_count": report["scenario_count"],
                    "passed_count": report["passed_count"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
