from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _default_plan() -> list[dict[str, Any]]:
    return [
        {
            "phase": "Phase 1 (Days 1-30)",
            "theme": "Production foundation",
            "goals": [
                "Stabilize CI quality gates with deterministic pass/fail criteria.",
                "Establish baseline security posture (SAST, dependency audit, secret scanning).",
                "Define service ownership map, on-call policy, and incident severity model.",
            ],
            "deliverables": [
                "Release readiness checklist linked to protected branch rules.",
                "Repository governance pack: CODEOWNERS, contribution flow, change control rubric.",
                "Quality scorecard with weekly trend snapshots.",
            ],
            "kpis": {
                "ci_success_rate": ">= 95%",
                "critical_vulnerability_sla": "0 open > 7 days",
                "mean_pr_review_time": "< 24h",
            },
        },
        {
            "phase": "Phase 2 (Days 31-60)",
            "theme": "Scale + reliability",
            "goals": [
                "Harden integration and end-to-end testing with flaky-test tracking.",
                "Operationalize observability and incident response drills.",
                "Introduce release train + rollback playbooks for critical workflows.",
            ],
            "deliverables": [
                "SLO dashboard and error budget policy for core workflows.",
                "Artifact evidence pack for reliability, security, and compliance audits.",
                "Automated release notes + deployment verification checklist.",
            ],
            "kpis": {
                "defect_escape_rate": "< 2%",
                "mttr": "< 60 minutes",
                "test_flake_rate": "< 3%",
            },
        },
        {
            "phase": "Phase 3 (Days 61-90)",
            "theme": "Governance + growth",
            "goals": [
                "Institutionalize engineering governance and architecture decision records.",
                "Expand contribution velocity without reducing quality gates.",
                "Publish executive-quality trust and readiness narrative.",
            ],
            "deliverables": [
                "Quarterly operating cadence (QBR, risk review, architecture council).",
                "Production excellence handbook for onboarding and cross-team consistency.",
                "Phase closeout board with next 90-day backlog and owners.",
            ],
            "kpis": {
                "change_failure_rate": "< 10%",
                "release_frequency": ">= weekly",
                "onboarding_time": "< 7 days to first meaningful contribution",
            },
        },
    ]


def build_phase_boost_payload(repo_name: str, start_date: str) -> dict[str, Any]:
    plan = _default_plan()
    return {
        "program": "S-class production readiness boost",
        "repository": repo_name,
        "start_date": start_date,
        "duration_days": 90,
        "quality_gates": [
            "All phase deliverables mapped to an owner and due date.",
            "Every KPI has a baseline value and weekly trend artifact.",
            "High/critical risks require rollback strategy and exec visibility.",
        ],
        "phases": plan,
    }


def _as_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# S-class production readiness — 90-day phase boost",
        "",
        f"- **Repository:** {payload['repository']}",
        f"- **Start date:** {payload['start_date']}",
        f"- **Duration:** {payload['duration_days']} days",
        "",
        "## Program quality gates",
        "",
    ]
    for gate in payload["quality_gates"]:
        lines.append(f"- {gate}")

    for phase in payload["phases"]:
        lines.extend(
            [
                "",
                f"## {phase['phase']} — {phase['theme']}",
                "",
                "### Goals",
            ]
        )
        for goal in phase["goals"]:
            lines.append(f"- {goal}")

        lines.extend(["", "### Deliverables"])
        for item in phase["deliverables"]:
            lines.append(f"- {item}")

        lines.extend(["", "### KPI targets"])
        for key, value in phase["kpis"].items():
            lines.append(f"- `{key}`: {value}")

    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit phase-boost",
        description="Generate a production-ready 90-day, 3-phase boost plan.",
    )
    parser.add_argument("--repo-name", default="DevS69-sdetkit", help="Repository name in output.")
    parser.add_argument("--start-date", default="TBD", help="Program start date label.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/artifacts/production-s-class-90-day-plan.md"),
        help="Markdown output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("docs/artifacts/production-s-class-90-day-plan.json"),
        help="JSON output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    payload = build_phase_boost_payload(repo_name=args.repo_name, start_date=args.start_date)
    markdown = _as_markdown(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(markdown, encoding="utf-8")
    args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[phase-boost] wrote {args.output}")
    print(f"[phase-boost] wrote {args.json_output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
