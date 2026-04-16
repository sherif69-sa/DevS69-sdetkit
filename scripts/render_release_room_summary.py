from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def build_release_room_summary(
    ship_summary: dict[str, Any], enterprise_summary: dict[str, Any] | None = None
) -> str:
    ship = ship_summary.get("summary", {}) if isinstance(ship_summary, dict) else {}
    decision = ship.get("decision", "unknown")
    blockers = ship.get("blockers", [])
    blocker_catalog = ship.get("blocker_catalog", [])

    lines = [
        "# Release room summary",
        "",
        f"- **Decision:** `{decision}`",
        f"- **All green:** `{ship.get('all_green')}`",
        f"- **Blockers:** {len(blockers) if isinstance(blockers, list) else 0}",
        "",
        "## Core lane status",
        "",
        "| Signal | Status |",
        "|---|---|",
        f"| gate fast | {'✅' if ship.get('gate_fast_ok') else '❌'} |",
        f"| gate release | {'✅' if ship.get('gate_release_ok') else '❌'} |",
        f"| doctor | {'✅' if ship.get('doctor_ok') else '❌'} |",
        f"| release readiness | {'✅' if ship.get('release_readiness_ok') else '❌'} |",
    ]

    if isinstance(blocker_catalog, list) and blocker_catalog:
        lines.extend(
            [
                "",
                "## Blocker catalog",
                "",
                "| Blocker | Error kind | Attempts | Return code |",
                "|---|---|---:|---:|",
            ]
        )
        for row in blocker_catalog:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"| `{row.get('id', 'unknown')}` | `{row.get('error_kind', 'unknown')}` | "
                f"{row.get('attempts', 0)} | {row.get('return_code', -1)} |"
            )

    if enterprise_summary and isinstance(enterprise_summary, dict):
        enterprise = enterprise_summary.get("summary", {})
        contract = enterprise_summary.get("upgrade_contract", {})
        lines.extend(
            [
                "",
                "## Enterprise signal",
                "",
                f"- **Enterprise score:** {enterprise.get('score', 'n/a')}",
                f"- **Tier:** `{enterprise.get('tier', 'n/a')}`",
                f"- **Risk band:** `{contract.get('risk_band', 'n/a')}`",
                f"- **Gate decision:** `{contract.get('gate_decision', 'n/a')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Recommended next action",
            "",
            (
                "- 🚀 Proceed to tagging and notes preparation."
                if decision == "go"
                else "- 🛑 Resolve blocker catalog items before release tag cut."
            ),
        ]
    )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a release-room markdown summary from JSON artifacts.")
    parser.add_argument("--ship-summary", type=Path, required=True)
    parser.add_argument("--enterprise-summary", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    ship = _load_json(args.ship_summary)
    enterprise = _load_json(args.enterprise_summary) if args.enterprise_summary else None
    markdown = build_release_room_summary(ship, enterprise)

    if args.out:
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
