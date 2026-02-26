from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import day37_experiment_lane as d37


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Day 37 experiment lane contract.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d37.build_day37_experiment_lane_summary(root)

    strict_failures: list[str] = []
    page = root / d37._PAGE_PATH
    page_text = page.read_text(encoding="utf-8") if page.exists() else ""
    for section in [d37._SECTION_HEADER, *d37._REQUIRED_SECTIONS]:
        if section not in page_text:
            strict_failures.append(section)
    for command in d37._REQUIRED_COMMANDS:
        if command not in page_text:
            strict_failures.append(command)
    for contract_line in d37._REQUIRED_CONTRACT_LINES:
        if f"- {contract_line}" not in page_text:
            strict_failures.append(contract_line)
    for quality_item in d37._REQUIRED_QUALITY_LINES:
        if quality_item not in page_text:
            strict_failures.append(quality_item)
    for board_item in d37._REQUIRED_DELIVERY_BOARD_LINES:
        if board_item not in page_text:
            strict_failures.append(board_item)

    errors: list[str] = []
    if strict_failures:
        errors.append(f"missing docs contract entries: {strict_failures}")
    if payload["summary"]["critical_failures"]:
        errors.append(f"critical failures: {payload['summary']['critical_failures']}")

    if not ns.skip_evidence:
        evidence = (
            root / "docs/artifacts/day37-experiment-lane-pack/evidence/day37-execution-summary.json"
        )
        if not evidence.exists():
            errors.append(f"missing evidence file: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if data.get("total_commands", 0) < 3:
                errors.append("execution evidence has insufficient commands")

    print(json.dumps({"errors": errors, "score": payload["summary"]["activation_score"]}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
