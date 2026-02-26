from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import day32_release_cadence as d32


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Day 32 release cadence contract.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d32.build_day32_release_cadence_summary(root)

    strict_failures: list[str] = []
    page = root / d32._PAGE_PATH
    page_text = page.read_text(encoding="utf-8") if page.exists() else ""
    for section in [d32._SECTION_HEADER, *d32._REQUIRED_SECTIONS]:
        if section not in page_text:
            strict_failures.append(section)
    for command in d32._REQUIRED_COMMANDS:
        if command not in page_text:
            strict_failures.append(command)
    for cadence_line in d32._REQUIRED_CADENCE_LINES:
        if f"- {cadence_line}" not in page_text:
            strict_failures.append(cadence_line)
    for changelog_item in d32._REQUIRED_CHANGELOG_LINES:
        if changelog_item not in page_text:
            strict_failures.append(changelog_item)
    for board_item in d32._REQUIRED_DELIVERY_BOARD_LINES:
        if board_item not in page_text:
            strict_failures.append(board_item)

    errors: list[str] = []
    if strict_failures:
        errors.append(f"missing docs contract entries: {strict_failures}")
    if payload["summary"]["critical_failures"]:
        errors.append(f"critical failures: {payload['summary']['critical_failures']}")

    if not ns.skip_evidence:
        evidence = (
            root / "docs/artifacts/day32-release-cadence-pack/evidence/day32-execution-summary.json"
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
