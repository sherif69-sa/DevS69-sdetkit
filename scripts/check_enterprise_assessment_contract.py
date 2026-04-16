from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = (
    "summary",
    "metrics",
    "checks",
    "boost_plan",
    "action_board",
    "upgrade_contract",
    "trend",
    "contract",
)

REQUIRED_SUMMARY_KEYS = ("score", "tier", "strict_pass")
REQUIRED_CONTRACT_KEYS = ("schema_version", "generated_at_utc", "contract_id")
REQUIRED_UPGRADE_KEYS = ("gate_decision", "risk_score", "risk_band", "sla_review_hours")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("summary file must be a JSON object")
    return payload


def check_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in REQUIRED_SUMMARY_KEYS:
            if key not in summary:
                errors.append(f"summary missing key: {key}")
    else:
        errors.append("summary must be an object")

    contract = payload.get("contract")
    if isinstance(contract, dict):
        for key in REQUIRED_CONTRACT_KEYS:
            if key not in contract:
                errors.append(f"contract missing key: {key}")
    else:
        errors.append("contract must be an object")

    upgrade = payload.get("upgrade_contract")
    if isinstance(upgrade, dict):
        for key in REQUIRED_UPGRADE_KEYS:
            if key not in upgrade:
                errors.append(f"upgrade_contract missing key: {key}")
    else:
        errors.append("upgrade_contract must be an object")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate enterprise-assessment summary contract.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = _load(args.summary)
    errors = check_contract(payload)
    result = {
        "ok": not errors,
        "errors": errors,
        "summary": str(args.summary),
    }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print("enterprise-assessment contract: ok")
        else:
            print("enterprise-assessment contract: fail")
            for row in errors:
                print(f"- {row}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
