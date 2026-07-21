from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit import _formatter_policy_proposal_observation_records as records
from sdetkit import _formatter_policy_proposal_observation_schema as schema

SCHEMA_VERSION = schema.REPORT_SCHEMA_VERSION
CONTRACT_SCHEMA_VERSION = schema.CONTRACT_SCHEMA_VERSION
OBSERVATIONS_SCHEMA_VERSION = schema.OBSERVATIONS_SCHEMA_VERSION
DEFAULT_CONTRACT = Path("docs/contracts/formatter-policy-proposal-observation.v1.json")
DEFAULT_OUT_DIR = Path("build") / "formatter-policy-proposal-observation"
REPORT_JSON = "formatter-policy-proposal-observation.json"
REPORT_MD = "formatter-policy-proposal-observation.md"
JsonObject = dict[str, Any]


def authority_boundary() -> dict[str, bool]:
    return schema.authority_boundary()


def build_report(
    observations_json: str | Path,
    *,
    contract_json: str | Path = DEFAULT_CONTRACT,
    root: str | Path = ".",
    current_head_sha: str | None = None,
    generator_path: str | Path | None = None,
) -> JsonObject:
    repo_root = Path(root).resolve()
    observations_path = Path(observations_json).resolve()
    contract_path = Path(contract_json).resolve()
    generator = Path(generator_path).resolve() if generator_path else Path(__file__).resolve()
    contract_payload = schema.load_object(contract_path, "observation contract")
    normalized, decisions, outcomes, definitions = records.normalize_observations(
        schema.load_object(observations_path, "formatter proposal observations"),
        contract_payload,
        repo_root,
    )
    head = schema.resolve_head(repo_root, current_head_sha)
    decision_counts = Counter({decision: 0 for decision in decisions})
    metric_counts = {
        item["metric_id"]: Counter({outcome: 0 for outcome in outcomes}) for item in definitions
    }
    for record in normalized:
        decision_counts[str(record["decision"])] += 1
        metric_outcomes = record["metric_outcomes"]
        if not isinstance(metric_outcomes, Mapping):
            raise ValueError("normalized metric outcomes must be an object")
        for metric_id, outcome in metric_outcomes.items():
            metric_counts[str(metric_id)][str(outcome)] += 1
    failed: list[str] = []
    metrics: list[JsonObject] = []
    for definition in definitions:
        metric_id = definition["metric_id"]
        counts = metric_counts[metric_id]
        applicable = counts["pass"] + counts["fail"]
        if counts["fail"]:
            failed.append(metric_id)
        metrics.append(
            {
                **definition,
                "reviewed_pass_observations": counts["pass"],
                "reviewed_fail_observations": counts["fail"],
                "reviewed_not_applicable_observations": counts["not_applicable"],
                "reviewed_applicable_observations": applicable,
                "pass_rate": round(counts["pass"] / applicable, 6) if applicable else None,
            }
        )
    if not normalized:
        next_action = "Review one real formatter policy proposal and retain its exact source artifact."
    elif failed:
        next_action = "Address failed proposal-quality dimensions before another observation."
    else:
        next_action = "Continue reviewed observations; keep the execution lane inactive."
    boundary = authority_boundary()
    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": "reviewed_observations_available" if normalized else "review_required",
        "observation_mode": "reporting_only",
        "input_provenance": schema.input_provenance(
            repo_root, observations_path, contract_path, head, generator
        ),
        "reviewed_observation_count": len(normalized),
        "decision_counts": {decision: decision_counts[decision] for decision in decisions},
        "metrics": metrics,
        "failed_metric_ids": sorted(failed),
        "false_authority_count": 0,
        "authority_validation": "validated_before_inclusion",
        "execution_research_ready": False,
        "branch_execution_lane_active": False,
        "broader_maturity_claim_allowed": False,
        "observations_authorize_current_action": False,
        "next_human_action": next_action,
        "observation_index": [
            {
                key: record[key]
                for key in (
                    "observation_id",
                    "proposal_path",
                    "proposal_sha256",
                    "source_repository",
                    "source_commit_sha",
                    "source_pr_number",
                    "reviewer_id",
                    "reviewed_at",
                    "decision",
                )
            }
            for record in normalized
        ],
        "rules": dict(contract_payload.get("rules", {})),
        "reporting_only": True,
        "source_authority": False,
        "authority_boundary": boundary,
        **boundary,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Formatter policy proposal observation",
        "",
        f"- Report status: `{schema.text(report.get('report_status'))}`",
        f"- Reviewed observation count: `{int(report.get('reviewed_observation_count', 0))}`",
        f"- False authority count: `{int(report.get('false_authority_count', 0))}`",
        f"- Execution research ready: `{str(bool(report.get('execution_research_ready'))).lower()}`",
        f"- Branch execution lane active: `{str(bool(report.get('branch_execution_lane_active'))).lower()}`",
        "",
        "| Dimension | Pass | Fail | Not applicable | Pass rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    metrics = report.get("metrics")
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, Mapping):
                continue
            lines.append(
                "| {metric_id} | {passed} | {failed} | {na} | {rate} |".format(
                    metric_id=schema.text(metric.get("metric_id")),
                    passed=int(metric.get("reviewed_pass_observations", 0)),
                    failed=int(metric.get("reviewed_fail_observations", 0)),
                    na=int(metric.get("reviewed_not_applicable_observations", 0)),
                    rate=(
                        "null" if metric.get("pass_rate") is None else metric.get("pass_rate")
                    ),
                )
            )
    return "\n".join(
        [
            *lines,
            "",
            "## Next human action",
            "",
            schema.text(report.get("next_human_action")),
            "",
        ]
    )


def write_report(
    observations_json: str | Path,
    *,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    **kwargs: Any,
) -> JsonObject:
    output = Path(out_dir).resolve()
    observations_path = Path(observations_json).resolve()
    if output == observations_path.parent or observations_path.parent in output.parents:
        raise ValueError("observation output must be outside source evidence directories")
    before = observations_path.read_bytes()
    report = build_report(observations_path, **kwargs)
    if observations_path.read_bytes() != before:
        raise ValueError("observation source was mutated while building the report")
    output.mkdir(parents=True, exist_ok=True)
    (output / REPORT_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / REPORT_MD).write_text(render_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.formatter_policy_proposal_observation"
    )
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--current-head-sha")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = write_report(
            args.observations,
            out_dir=args.out_dir,
            contract_json=args.contract_json,
            root=args.root,
            current_head_sha=args.current_head_sha,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"report_status: {report['report_status']}")
        print(f"reviewed_observation_count: {report['reviewed_observation_count']}")
        print(f"false_authority_count: {report['false_authority_count']}")
        print(
            "branch_execution_lane_active: "
            f"{str(report['branch_execution_lane_active']).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
