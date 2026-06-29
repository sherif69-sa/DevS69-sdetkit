from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = ".".join(("sdetkit", "benchmark_control_scorecard", "v1"))
DEFAULT_OUT_DIR = Path("build") / "benchmark-control-scorecard"
SCORECARD_JSON = "benchmark-control-scorecard.json"
SCORECARD_MD = "benchmark-control-scorecard.md"

SCORECARD_TYPE = "_".join(("benchmark", "control"))
DEFAULT_REPORT_MODE = "_".join(("default", "fixture"))
CURRENT_PR_DECISION_INPUT = "_".join(("current", "pr", "decision", "input"))
SEMANTIC_EQUIVALENCE_PROVEN = "_".join(("semantic", "equivalence", "proven"))
SEMANTIC_EQUIVALENCE_CLAIMED_COUNT = "_".join(("semantic", "equivalence", "claimed", "count"))
AUTHORITY_EXPANSION_COUNT = "_".join(("authority", "expansion", "count"))
CONTRIBUTES_TO_CURRENT_PR_DECISION = "_".join(("contributes", "to", "current", "pr", "decision"))
FEEDS_REPO_MEMORY = "_".join(("feeds", "repo", "memory"))
EXECUTES_PLAN = "_".join(("executes", "plan"))
EXECUTES_PATCH = "_".join(("executes", "patch"))

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


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percent(numerator: int, denominator: int) -> float:
    return round(_rate(numerator, denominator) * 100.0, 2)


def _read_json(path: Path) -> JsonObject:
    if not path.is_file():
        raise ValueError(f"benchmark report does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"benchmark report must be a JSON object: {path}")
    return payload


def _required_contract_passed(report: Mapping[str, Any]) -> bool:
    contract = _as_dict(report.get("required_contract"))
    return (
        bool(contract)
        and _bool(contract.get("all_required_present"))
        and _bool(contract.get("all_required_passed"))
    )


def _boundary_expansion_fields(boundary: Mapping[str, Any]) -> list[str]:
    boolean_fields = (
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        SEMANTIC_EQUIVALENCE_PROVEN,
        CONTRIBUTES_TO_CURRENT_PR_DECISION,
        CURRENT_PR_DECISION_INPUT,
        FEEDS_REPO_MEMORY,
        EXECUTES_PLAN,
        EXECUTES_PATCH,
    )
    count_fields = (
        "automation_allowed_count",
        "merge_authorized_count",
        SEMANTIC_EQUIVALENCE_CLAIMED_COUNT,
        AUTHORITY_EXPANSION_COUNT,
        "runtime_proof_contract_authority_expansion_count",
    )

    expanded = [field for field in boolean_fields if _bool(boundary.get(field))]
    expanded.extend(field for field in count_fields if _int(boundary.get(field)) > 0)
    return sorted(set(expanded))


def _normalize_report(
    report: Mapping[str, Any],
    *,
    source_path: str,
) -> JsonObject:
    schema_version = _string(report.get("schema_version"))
    if not schema_version:
        raise ValueError(f"schema_version is required in {source_path}")

    report_mode = _string(report.get("report_mode")) or DEFAULT_REPORT_MODE
    status = _string(report.get("status"))
    if status not in {"passed", "failed"}:
        raise ValueError(f"benchmark status must be passed or failed in {source_path}")

    scenario_count = _int(report.get("scenario_count"))
    passed_count = _int(report.get("passed_count"))
    failed_count = _int(report.get("failed_count"))
    if min(scenario_count, passed_count, failed_count) < 0:
        raise ValueError(f"benchmark counts cannot be negative in {source_path}")
    if passed_count + failed_count != scenario_count:
        raise ValueError(
            f"benchmark counts are inconsistent in {source_path}: "
            f"{passed_count}+{failed_count}!={scenario_count}"
        )

    required_contract = _as_dict(report.get("required_contract"))
    if not required_contract:
        raise ValueError(f"required_contract is required in {source_path}")

    safety_boundary = _as_dict(report.get("safety_boundary"))
    if not safety_boundary:
        raise ValueError(f"safety_boundary is required in {source_path}")

    expanded_fields = _boundary_expansion_fields(safety_boundary)
    boundary_preserved = _bool(safety_boundary.get("preserved")) and not expanded_fields

    return {
        "source_path": source_path,
        "schema_version": schema_version,
        "report_mode": report_mode,
        "status": status,
        "scenario_count": scenario_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "scenario_pass_rate": _rate(passed_count, scenario_count),
        "required_contract_passed": _required_contract_passed(report),
        "boundary_preserved": boundary_preserved,
        "expanded_authority_fields": expanded_fields,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        SEMANTIC_EQUIVALENCE_PROVEN: False,
    }


def load_benchmark_reports(paths: Sequence[Path]) -> list[JsonObject]:
    if not paths:
        raise ValueError("at least one benchmark report is required")

    reports: list[JsonObject] = []
    identities: set[tuple[str, str]] = set()
    for path in paths:
        normalized = _normalize_report(
            _read_json(path),
            source_path=path.as_posix(),
        )
        identity = (
            _string(normalized.get("schema_version")),
            _string(normalized.get("report_mode")),
        )
        if identity in identities:
            raise ValueError(f"duplicate benchmark report identity: {identity[0]}::{identity[1]}")
        identities.add(identity)
        reports.append(normalized)

    return reports


def build_scorecard(reports: Sequence[Mapping[str, Any]]) -> JsonObject:
    if not reports:
        raise ValueError("at least one normalized benchmark report is required")

    normalized = [dict(item) for item in reports]
    report_count = len(normalized)
    passed_report_count = sum(1 for item in normalized if item.get("status") == "passed")
    scenario_count = sum(_int(item.get("scenario_count")) for item in normalized)
    passed_scenario_count = sum(_int(item.get("passed_count")) for item in normalized)
    failed_scenario_count = sum(_int(item.get("failed_count")) for item in normalized)
    required_contract_pass_count = sum(
        1 for item in normalized if _bool(item.get("required_contract_passed"))
    )
    boundary_preserved_count = sum(
        1 for item in normalized if _bool(item.get("boundary_preserved"))
    )

    dimensions = {
        "report_status": _percent(passed_report_count, report_count),
        "scenario_health": _percent(passed_scenario_count, scenario_count),
        "required_contracts": _percent(
            required_contract_pass_count,
            report_count,
        ),
        "safety_boundaries": _percent(
            boundary_preserved_count,
            report_count,
        ),
    }
    overall_score = round(sum(dimensions.values()) / len(dimensions), 2)
    passed = overall_score == 100.0 and scenario_count > 0 and failed_scenario_count == 0

    expanded_fields = sorted(
        {
            _string(field)
            for item in normalized
            for field in _as_list(item.get("expanded_authority_fields"))
            if _string(field)
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "scorecard_type": SCORECARD_TYPE,
        "overall_score": overall_score,
        "dimension_scores": dimensions,
        "report_count": report_count,
        "passed_report_count": passed_report_count,
        "failed_report_count": report_count - passed_report_count,
        "scenario_count": scenario_count,
        "passed_scenario_count": passed_scenario_count,
        "failed_scenario_count": failed_scenario_count,
        "scenario_pass_rate": _rate(
            passed_scenario_count,
            scenario_count,
        ),
        "required_contract_pass_count": required_contract_pass_count,
        "boundary_preserved_count": boundary_preserved_count,
        "benchmark_modes": sorted(
            {
                _string(item.get("report_mode"))
                for item in normalized
                if _string(item.get("report_mode"))
            }
        ),
        "expanded_authority_fields": expanded_fields,
        "reports": normalized,
        "decision_boundary": {
            "reporting_only": True,
            CURRENT_PR_DECISION_INPUT: False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
            EXECUTES_PLAN: False,
            EXECUTES_PATCH: False,
        },
        "next_boundary": (
            "Compare scorecards against an explicit reviewed baseline before "
            "introducing any regression gate."
        ),
    }


def render_markdown(scorecard: Mapping[str, Any]) -> str:
    dimensions = _as_dict(scorecard.get("dimension_scores"))
    reports = [_as_dict(item) for item in _as_list(scorecard.get("reports")) if _as_dict(item)]
    boundary = _as_dict(scorecard.get("decision_boundary"))

    lines = [
        "# Benchmark Control Scorecard",
        "",
        f"- Status: `{_string(scorecard.get('status'))}`",
        (f"- Overall score: `{float(scorecard.get('overall_score', 0.0) or 0.0):.2f}`"),
        f"- Reports: `{_int(scorecard.get('report_count'))}`",
        f"- Scenarios: `{_int(scorecard.get('scenario_count'))}`",
        (f"- Scenario pass rate: `{float(scorecard.get('scenario_pass_rate', 0.0) or 0.0):.4f}`"),
        "",
        "## Dimension scores",
        "",
        "| Dimension | Score |",
        "|---|---:|",
    ]
    for name, value in sorted(dimensions.items()):
        lines.append(f"| `{name}` | `{float(value or 0.0):.2f}` |")

    lines.extend(
        [
            "",
            "## Benchmark reports",
            "",
            "| Mode | Schema | Status | Scenarios | Required contract | Boundary |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for item in reports:
        lines.append(
            "| "
            f"`{_string(item.get('report_mode'))}` | "
            f"`{_string(item.get('schema_version'))}` | "
            f"`{_string(item.get('status'))}` | "
            f"`{_int(item.get('scenario_count'))}` | "
            f"`{str(_bool(item.get('required_contract_passed'))).lower()}` | "
            f"`{str(_bool(item.get('boundary_preserved'))).lower()}` |"
        )

    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            (f"- Reporting only: `{str(_bool(boundary.get('reporting_only'))).lower()}`"),
            (
                "- Current PR decision input: "
                f"`{str(_bool(boundary.get(CURRENT_PR_DECISION_INPUT))).lower()}`"
            ),
            (f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`"),
            (f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`"),
            (f"- Executes plan: `{str(_bool(boundary.get(EXECUTES_PLAN))).lower()}`"),
            "",
            f"Next boundary: {_string(scorecard.get('next_boundary'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_scorecard(
    scorecard: Mapping[str, Any],
    *,
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SCORECARD_JSON
    markdown_path = out_dir / SCORECARD_MD
    json_path.write_text(
        json.dumps(dict(scorecard), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(scorecard), encoding="utf-8")
    return json_path, markdown_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate replayable benchmark reports into a reporting-only control scorecard."
        )
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        action="append",
        required=True,
        help="Replayable benchmark report JSON. Repeat for each report mode.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        reports = load_benchmark_reports(args.benchmark_report)
        scorecard = build_scorecard(reports)
        write_scorecard(scorecard, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark control scorecard failed: {exc}")
        return 2

    if args.format == "markdown":
        print(render_markdown(scorecard), end="")
    else:
        print(json.dumps(scorecard, indent=2, sort_keys=True))

    return 0 if scorecard.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
