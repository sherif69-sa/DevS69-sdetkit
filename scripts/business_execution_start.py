#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-start.v1"


def _today_utc() -> date:
    return datetime.now(UTC).date()


def build_payload(
    *,
    start_date: date,
    program_owner: str,
    gtm_owner: str,
    commercial_owner: str,
    solutions_owner: str,
    ops_owner: str,
) -> dict[str, Any]:
    owner_values = [
        program_owner.strip(),
        gtm_owner.strip(),
        commercial_owner.strip(),
        solutions_owner.strip(),
        ops_owner.strip(),
    ]
    owners_assigned = all(value and value.upper() != "TBD" for value in owner_values)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "start_date": start_date.isoformat(),
        "owners": {
            "program_owner": program_owner,
            "gtm_owner": gtm_owner,
            "commercial_owner": commercial_owner,
            "solutions_owner": solutions_owner,
            "ops_owner": ops_owner,
        },
        "week_1_execution_plan": {
            "day_1": [
                "Confirm owners and operating cadence.",
                "Finalize ICP shortlist.",
            ],
            "day_2_3": [
                "Run first discovery block.",
                "Capture baseline KPI values.",
            ],
            "day_4_5": [
                "Draft pilot charter for top candidate.",
                "Publish week-1 operating memo.",
            ],
        },
        "kpi_baseline_template": [
            {"kpi": "qualified_accounts", "value": None, "owner": gtm_owner},
            {"kpi": "discovery_to_pilot_rate", "value": None, "owner": gtm_owner},
            {"kpi": "pilot_time_to_value_days", "value": None, "owner": solutions_owner},
            {"kpi": "pilot_to_paid_rate", "value": None, "owner": commercial_owner},
            {"kpi": "weekly_operating_memo_on_time", "value": None, "owner": program_owner},
            {"kpi": "dashboard_data_quality_score", "value": None, "owner": ops_owner},
        ],
        "status": "go" if owners_assigned else "needs-owner-assignment",
        "next_action": (
            "Run execution week with live owners and baseline KPIs."
            if owners_assigned
            else "Assign all owners, then rerun this command."
        ),
    }


def render_weekly_memo(payload: dict[str, Any]) -> str:
    owners = payload["owners"]
    start_date = payload["start_date"]
    status = str(payload.get("status", "needs-owner-assignment")).upper()
    next_action = str(payload.get("next_action", "Assign owners and rerun command."))
    return "\n".join(
        [
            "# Business Execution Week-1 Operating Memo",
            "",
            f"- Start date: {start_date}",
            f"- Program owner: {owners['program_owner']}",
            f"- GTM owner: {owners['gtm_owner']}",
            f"- Commercial owner: {owners['commercial_owner']}",
            f"- Solutions owner: {owners['solutions_owner']}",
            f"- Ops owner: {owners['ops_owner']}",
            "",
            "## Day 1",
            "- Confirm owners and operating cadence.",
            "- Finalize ICP shortlist.",
            "",
            "## Day 2-3",
            "- Run first discovery block.",
            "- Capture baseline KPI values.",
            "",
            "## Day 4-5",
            "- Draft pilot charter for top candidate.",
            "- Publish week-1 operating memo.",
            "",
            "## End-of-week gate decision",
            f"- Status: {status}",
            "- Required evidence: KPI snapshot, owner signoff, risk review, next-step plan.",
            f"- Next action: {next_action}",
            "",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap executable business-execution week-1 artifacts."
    )
    parser.add_argument(
        "--start-date",
        default=_today_utc().isoformat(),
        help="Week-1 start date in YYYY-MM-DD format (default: today UTC).",
    )
    parser.add_argument("--program-owner", default="TBD")
    parser.add_argument("--gtm-owner", default="TBD")
    parser.add_argument("--commercial-owner", default="TBD")
    parser.add_argument("--solutions-owner", default="TBD")
    parser.add_argument("--ops-owner", default="TBD")
    parser.add_argument(
        "--single-operator",
        default=None,
        help="Assign one operator to all owner roles so only one person drives execution.",
    )
    parser.add_argument(
        "--out-json",
        default="build/business-execution/business-execution-week1.json",
    )
    parser.add_argument(
        "--out-memo",
        default="build/business-execution/business-execution-week1-memo.md",
    )
    parser.add_argument(
        "--strict-owner-assignment",
        action="store_true",
        help="Return non-zero when owners are not fully assigned.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start_date = date.fromisoformat(args.start_date)
    program_owner = args.program_owner
    gtm_owner = args.gtm_owner
    commercial_owner = args.commercial_owner
    solutions_owner = args.solutions_owner
    ops_owner = args.ops_owner
    if args.single_operator:
        operator = args.single_operator.strip()
        if operator:
            program_owner = operator
            gtm_owner = operator
            commercial_owner = operator
            solutions_owner = operator
            ops_owner = operator
    payload = build_payload(
        start_date=start_date,
        program_owner=program_owner,
        gtm_owner=gtm_owner,
        commercial_owner=commercial_owner,
        solutions_owner=solutions_owner,
        ops_owner=ops_owner,
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    out_memo = Path(args.out_memo)
    out_memo.parent.mkdir(parents=True, exist_ok=True)
    out_memo.write_text(render_weekly_memo(payload), encoding="utf-8")
    print(f"business-execution-start: wrote {out_json} and {out_memo}")
    if args.strict_owner_assignment and payload["status"] != "go":
        print("business-execution-start: owner assignment incomplete (strict mode).")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
