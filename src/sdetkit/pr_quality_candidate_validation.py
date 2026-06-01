from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit.pr_quality_candidate_visibility import (
    build_candidate_visibility,
)
from sdetkit.pr_quality_candidate_visibility import (
    render_markdown as render_candidate_markdown,
)

SCHEMA_VERSION = "sdetkit.pr_quality.candidate_validation.v1"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "candidate-validation"
REPORT_JSON = "candidate-validation.json"
REPORT_MD = "candidate-validation.md"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _read_scenario(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    if not _string(payload.get("scenario_id")):
        raise ValueError(f"scenario_id is required in {path}")
    if not _string(payload.get("expected_status")):
        raise ValueError(f"expected_status is required in {path}")
    if not _string(payload.get("expected_verifier_status")):
        raise ValueError(f"expected_verifier_status is required in {path}")
    return payload


def evaluate_scenario(payload: Mapping[str, Any], *, source_path: Path) -> JsonObject:
    visibility = build_candidate_visibility(
        check_intelligence=_as_dict(payload.get("check_intelligence")),
        evidence_graph=_as_dict(payload.get("evidence_graph")),
        pr_quality_action_report=_as_dict(payload.get("pr_quality_action_report")),
        changed_files=[_string(item) for item in _as_list(payload.get("changed_files"))],
        pattern_insights=_as_dict(payload.get("pattern_insights")),
        verification_evidence=_as_dict(payload.get("verification_evidence")),
    )
    decision = _as_dict(visibility.get("decision_boundary"))
    verifier = _as_dict(_as_dict(visibility.get("protected_verifier")).get("decision"))
    rendered = render_candidate_markdown(visibility)
    expected_status = _string(payload.get("expected_status"))
    expected_verifier_status = _string(payload.get("expected_verifier_status"))
    passed = (
        visibility.get("status") == expected_status
        and verifier.get("status") == expected_verifier_status
        and decision.get("automation_allowed") is False
        and decision.get("merge_authorized") is False
        and decision.get("semantic_equivalence_proven") is False
        and verifier.get("automation_allowed") is False
        and verifier.get("merge_authorized") is False
        and rendered.startswith("## Read-only remediation candidate verification\n")
    )
    return {
        "scenario_id": _string(payload.get("scenario_id")),
        "source_path": source_path.as_posix(),
        "expected_status": expected_status,
        "observed_status": _string(visibility.get("status")),
        "expected_verifier_status": expected_verifier_status,
        "observed_verifier_status": _string(verifier.get("status")),
        "candidate_renderer_exercised": bool(rendered),
        "candidate_markdown": rendered,
        "automation_allowed": bool(decision.get("automation_allowed", False)),
        "merge_authorized": bool(decision.get("merge_authorized", False)),
        "semantic_equivalence_proven": bool(decision.get("semantic_equivalence_proven", False)),
        "passed": passed,
    }


def build_family_evaluation(scenarios: Sequence[Mapping[str, Any]]) -> JsonObject:
    structurally_verified = sum(
        1
        for scenario in scenarios
        if _string(scenario.get("observed_status")) == "candidate_structurally_verified"
        and _string(scenario.get("observed_verifier_status")) == "structurally_verified_candidate"
        and scenario.get("passed") is True
    )
    review_first_blocked = sum(
        1
        for scenario in scenarios
        if _string(scenario.get("observed_status")) == "candidate_review_first_after_verification"
        and _string(scenario.get("observed_verifier_status")) == "blocked_review_first"
        and scenario.get("passed") is True
    )
    return {
        "schema_version": "sdetkit.formatting_candidate_family_evaluation.v1",
        "family": "formatting_only",
        "evaluation_mode": "read_only_without_writes",
        "scenario_count": len(scenarios),
        "passed_count": sum(1 for scenario in scenarios if scenario.get("passed") is True),
        "structurally_verified_count": structurally_verified,
        "review_first_blocked_count": review_first_blocked,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "current_pr_decision_input": False,
    }


def build_validation_report(scenario_paths: Sequence[Path]) -> JsonObject:
    scenarios = [
        evaluate_scenario(_read_scenario(path), source_path=path) for path in scenario_paths
    ]
    passed_count = sum(1 for scenario in scenarios if scenario["passed"] is True)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed_count == len(scenarios) else "failed",
        "scenario_count": len(scenarios),
        "passed_count": passed_count,
        "scenarios": scenarios,
        "family_evaluation": build_family_evaluation(scenarios),
        "boundary": {
            "controlled_fixture_inputs_only": True,
            "contributes_to_current_pr_decision": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    boundary = _as_dict(report.get("boundary"))
    family = _as_dict(report.get("family_evaluation"))
    lines = [
        "## Controlled read-only candidate evidence validation",
        "",
        "- Evidence type: `deterministic_fixture_validation`",
        "- Current PR decision input: `false`",
        f"- Validation status: `{_string(report.get('status') or 'unknown')}`",
        f"- Scenarios passed: `{int(report.get('passed_count', 0) or 0)}/{int(report.get('scenario_count', 0) or 0)}`",
        f"- Automation allowed: `{str(bool(boundary.get('automation_allowed', False))).lower()}`",
        f"- Merge authorized: `{str(bool(boundary.get('merge_authorized', False))).lower()}`",
        (
            "- Semantic equivalence proven: "
            f"`{str(bool(boundary.get('semantic_equivalence_proven', False))).lower()}`"
        ),
        "- Interpretation: this section validates the read-only evidence renderer; it does not identify a remediation candidate in the current PR.",
        "",
        "### Formatting-only family evaluation",
        "",
        f"- Family: `{_string(family.get('family') or 'unknown')}`",
        f"- Evaluation mode: `{_string(family.get('evaluation_mode') or 'unknown')}`",
        f"- Structurally verified candidates: `{int(family.get('structurally_verified_count', 0) or 0)}`",
        f"- Review-first blocked candidates: `{int(family.get('review_first_blocked_count', 0) or 0)}`",
        (
            "- Patch application allowed: "
            f"`{str(bool(family.get('patch_application_allowed', False))).lower()}`"
        ),
        f"- Automation allowed: `{str(bool(family.get('automation_allowed', False))).lower()}`",
        f"- Merge authorized: `{str(bool(family.get('merge_authorized', False))).lower()}`",
        "",
        "### Controlled scenario outcomes",
        "",
    ]
    for scenario in _as_list(report.get("scenarios")):
        row = _as_dict(scenario)
        lines.extend(
            [
                f"- `{_string(row.get('scenario_id'))}`: "
                f"status=`{_string(row.get('observed_status'))}`, "
                f"verifier=`{_string(row.get('observed_verifier_status'))}`, "
                f"passed=`{str(bool(row.get('passed', False))).lower()}`, "
                "automation_allowed=`false`, merge_authorized=`false`",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / REPORT_JSON
    markdown_path = out_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {
        "candidate_validation_json": json_path.as_posix(),
        "candidate_validation_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_candidate_validation")
    parser.add_argument("--scenario", action="append", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_validation_report(args.scenario)
        artifacts = write_report(report, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "scenario_count": report["scenario_count"],
                    "passed_count": report["passed_count"],
                    "family_evaluation": report["family_evaluation"],
                    "boundary": report["boundary"],
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status: {report['status']}")
        print(f"scenarios: {report['passed_count']}/{report['scenario_count']}")

    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
