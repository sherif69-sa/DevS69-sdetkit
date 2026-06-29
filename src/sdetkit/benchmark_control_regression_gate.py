from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import benchmark_control_scorecard

SCHEMA_VERSION = ".".join(("sdetkit", "benchmark_control_regression_gate", "v1"))
BASELINE_SCHEMA_VERSION = ".".join(("sdetkit", "benchmark_control_baseline", "v1"))
DEFAULT_BASELINE_PATH = Path(".sdetkit") / "benchmark-control-baseline.json"
DEFAULT_OUT_DIR = Path("build") / "benchmark-control-regression-gate"
REPORT_JSON = "benchmark-control-regression.json"
REPORT_MD = "benchmark-control-regression.md"

GATE_TYPE = "_".join(("reviewed", "baseline", "regression"))
CURRENT_PR_DECISION_INPUT = "_".join(("current", "pr", "decision", "input"))
SEMANTIC_EQUIVALENCE_PROVEN = "_".join(("semantic", "equivalence", "proven"))
EXECUTES_PLAN = "_".join(("executes", "plan"))
EXECUTES_PATCH = "_".join(("executes", "patch"))
EXPANDED_AUTHORITY_FIELDS = "_".join(("expanded", "authority", "fields"))

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> JsonObject:
    if not path.is_file():
        raise ValueError(f"JSON input does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def load_scorecard(path: Path) -> JsonObject:
    payload = _read_json(path)
    if payload.get("schema_version") != benchmark_control_scorecard.SCHEMA_VERSION:
        raise ValueError(f"unsupported scorecard schema: {_string(payload.get('schema_version'))}")
    if not _as_dict(payload.get("dimension_scores")):
        raise ValueError("scorecard dimension_scores are required")
    if not _as_dict(payload.get("decision_boundary")):
        raise ValueError("scorecard decision_boundary is required")
    return payload


def load_baseline(path: Path) -> JsonObject:
    payload = _read_json(path)
    if payload.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ValueError(f"unsupported baseline schema: {_string(payload.get('schema_version'))}")
    if not _string(payload.get("baseline_id")):
        raise ValueError("baseline_id is required")

    activation = _as_dict(payload.get("activation"))
    if activation.get("model") != "protected_main_merge":
        raise ValueError("baseline activation model must be protected_main_merge")
    if not _bool(activation.get("requires_human_review")):
        raise ValueError("baseline must require human review")
    if _bool(activation.get("automatic_updates_allowed")):
        raise ValueError("automatic baseline updates are not allowed")

    minimums = _as_dict(payload.get("minimums"))
    dimensions = _as_dict(minimums.get("dimension_scores"))
    if not minimums or not dimensions:
        raise ValueError("baseline minimums and dimension scores are required")

    required_modes = sorted(
        {
            _string(item)
            for item in _as_list(payload.get("required_benchmark_modes"))
            if _string(item)
        }
    )
    if not required_modes:
        raise ValueError("at least one required benchmark mode is required")

    authority = _as_dict(payload.get("authority_contract"))
    if not authority:
        raise ValueError("baseline authority_contract is required")
    if not _bool(authority.get("reporting_only")):
        raise ValueError("baseline authority must remain reporting-only")
    if _as_list(authority.get(EXPANDED_AUTHORITY_FIELDS)):
        raise ValueError("baseline cannot allow expanded authority fields")

    return payload


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


def build_regression_report(
    scorecard: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    scorecard_path: str = "",
    baseline_path: str = "",
) -> JsonObject:
    minimums = _as_dict(baseline.get("minimums"))
    minimum_dimensions = _as_dict(minimums.get("dimension_scores"))
    candidate_dimensions = _as_dict(scorecard.get("dimension_scores"))
    candidate_boundary = _as_dict(scorecard.get("decision_boundary"))
    authority_contract = _as_dict(baseline.get("authority_contract"))

    candidate_modes = sorted(
        {_string(item) for item in _as_list(scorecard.get("benchmark_modes")) if _string(item)}
    )
    required_modes = sorted(
        {
            _string(item)
            for item in _as_list(baseline.get("required_benchmark_modes"))
            if _string(item)
        }
    )
    missing_modes = sorted(set(required_modes) - set(candidate_modes))

    checks: list[JsonObject] = [
        _check(
            name="scorecard_schema",
            passed=scorecard.get("schema_version") == benchmark_control_scorecard.SCHEMA_VERSION,
            expected=benchmark_control_scorecard.SCHEMA_VERSION,
            actual=_string(scorecard.get("schema_version")),
        ),
        _check(
            name="scorecard_status",
            passed=scorecard.get("status") == "passed",
            expected="passed",
            actual=_string(scorecard.get("status")),
        ),
        _check(
            name="overall_score",
            passed=_float(scorecard.get("overall_score")) >= _float(minimums.get("overall_score")),
            expected=_float(minimums.get("overall_score")),
            actual=_float(scorecard.get("overall_score")),
        ),
        _check(
            name="scenario_pass_rate",
            passed=_float(scorecard.get("scenario_pass_rate"))
            >= _float(minimums.get("scenario_pass_rate")),
            expected=_float(minimums.get("scenario_pass_rate")),
            actual=_float(scorecard.get("scenario_pass_rate")),
        ),
        _check(
            name="report_count",
            passed=_int(scorecard.get("report_count")) >= _int(minimums.get("report_count")),
            expected=_int(minimums.get("report_count")),
            actual=_int(scorecard.get("report_count")),
        ),
        _check(
            name="scenario_count",
            passed=_int(scorecard.get("scenario_count")) >= _int(minimums.get("scenario_count")),
            expected=_int(minimums.get("scenario_count")),
            actual=_int(scorecard.get("scenario_count")),
        ),
        _check(
            name="required_modes",
            passed=not missing_modes,
            expected=required_modes,
            actual=candidate_modes,
        ),
        _check(
            name="expanded_authority",
            passed=not _as_list(scorecard.get(EXPANDED_AUTHORITY_FIELDS)),
            expected=[],
            actual=_as_list(scorecard.get(EXPANDED_AUTHORITY_FIELDS)),
        ),
    ]

    for name, minimum in sorted(minimum_dimensions.items()):
        checks.append(
            _check(
                name=f"dimension:{name}",
                passed=_float(candidate_dimensions.get(name)) >= _float(minimum),
                expected=_float(minimum),
                actual=_float(candidate_dimensions.get(name)),
            )
        )

    for field, expected in sorted(authority_contract.items()):
        if field == EXPANDED_AUTHORITY_FIELDS:
            continue
        checks.append(
            _check(
                name=f"authority:{field}",
                passed=candidate_boundary.get(field) is expected,
                expected=expected,
                actual=candidate_boundary.get(field),
            )
        )

    regressions = [
        {
            "check": _string(item.get("name")),
            "expected": item.get("expected"),
            "actual": item.get("actual"),
        }
        for item in checks
        if not _bool(item.get("passed"))
    ]
    passed = not regressions

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "gate_type": GATE_TYPE,
        "regression_detected": not passed,
        "regression_count": len(regressions),
        "baseline": {
            "path": baseline_path,
            "baseline_id": _string(baseline.get("baseline_id")),
            "schema_version": _string(baseline.get("schema_version")),
            "activation": _as_dict(baseline.get("activation")),
            "required_benchmark_modes": required_modes,
            "minimums": minimums,
        },
        "candidate": {
            "path": scorecard_path,
            "schema_version": _string(scorecard.get("schema_version")),
            "status": _string(scorecard.get("status")),
            "overall_score": _float(scorecard.get("overall_score")),
            "dimension_scores": candidate_dimensions,
            "report_count": _int(scorecard.get("report_count")),
            "scenario_count": _int(scorecard.get("scenario_count")),
            "scenario_pass_rate": _float(scorecard.get("scenario_pass_rate")),
            "benchmark_modes": candidate_modes,
            EXPANDED_AUTHORITY_FIELDS: _as_list(scorecard.get(EXPANDED_AUTHORITY_FIELDS)),
        },
        "checks": checks,
        "regressions": regressions,
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
        "next_action": (
            "Human review is required before changing the candidate or "
            "updating the protected-main baseline."
            if regressions
            else "No benchmark-control regression was detected."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    baseline = _as_dict(report.get("baseline"))
    candidate = _as_dict(report.get("candidate"))
    boundary = _as_dict(report.get("decision_boundary"))
    checks = [_as_dict(item) for item in _as_list(report.get("checks")) if _as_dict(item)]

    lines = [
        "# Benchmark Control Regression Gate",
        "",
        f"- Status: `{_string(report.get('status'))}`",
        (f"- Regression detected: `{str(_bool(report.get('regression_detected'))).lower()}`"),
        f"- Regression count: `{_int(report.get('regression_count'))}`",
        f"- Baseline: `{_string(baseline.get('baseline_id'))}`",
        (f"- Candidate overall score: `{_float(candidate.get('overall_score')):.2f}`"),
        "",
        "## Checks",
        "",
        "| Check | Passed | Expected | Actual |",
        "|---|---|---|---|",
    ]
    for item in checks:
        lines.append(
            "| "
            f"`{_string(item.get('name'))}` | "
            f"`{str(_bool(item.get('passed'))).lower()}` | "
            f"`{json.dumps(item.get('expected'), sort_keys=True)}` | "
            f"`{json.dumps(item.get('actual'), sort_keys=True)}` |"
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
            "",
            f"Next action: {_string(report.get('next_action'))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    report: Mapping[str, Any],
    *,
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / REPORT_JSON
    markdown_path = out_dir / REPORT_MD
    json_path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return json_path, markdown_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a benchmark control scorecard with a protected-main reviewed baseline."
        )
    )
    parser.add_argument(
        "--scorecard",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
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
        scorecard = load_scorecard(args.scorecard)
        baseline = load_baseline(args.baseline)
        report = build_regression_report(
            scorecard,
            baseline,
            scorecard_path=args.scorecard.as_posix(),
            baseline_path=args.baseline.as_posix(),
        )
        write_report(report, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark control regression gate failed: {exc}")
        return 2

    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
