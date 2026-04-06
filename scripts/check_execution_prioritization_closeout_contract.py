from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import execution_prioritization_closeout_50 as d50


def _resolve_evidence_path(root: Path) -> Path:
    canonical = (
        root
        / "docs/artifacts/execution-prioritization-closeout-pack/evidence/execution-prioritization-execution-summary.json"
    )
    if canonical.exists():
        return canonical
    return (
        root
        / "docs/artifacts/execution-prioritization-closeout-pack-50/evidence/execution-summary-50.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate execution prioritization closeout contract "
            "(legacy alias: cycle50 execution prioritization closeout)."
        )
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d50.build_execution_prioritization_closeout_summary(root)

    strict_failures: list[str] = []
    page = root / d50._PAGE_PATH
    page_text = page.read_text(encoding="utf-8") if page.exists() else ""
    for section in [d50._SECTION_HEADER, *d50._REQUIRED_SECTIONS]:
        if section not in page_text:
            strict_failures.append(section)
    for command in d50._REQUIRED_COMMANDS:
        if command not in page_text:
            strict_failures.append(command)
    for contract_line in d50._REQUIRED_CONTRACT_LINES:
        if f"- {contract_line}" not in page_text:
            strict_failures.append(contract_line)
    for quality_item in d50._REQUIRED_QUALITY_LINES:
        if quality_item not in page_text:
            strict_failures.append(quality_item)
    for board_item in d50._REQUIRED_DELIVERY_BOARD_LINES:
        if board_item not in page_text:
            strict_failures.append(board_item)

    errors: list[str] = []
    if strict_failures:
        errors.append(f"missing docs contract entries: {strict_failures}")
    if payload["summary"]["critical_failures"]:
        errors.append(f"critical failures: {payload['summary']['critical_failures']}")

    if not ns.skip_evidence:
        evidence = _resolve_evidence_path(root)
        if not evidence.exists():
            errors.append(f"missing evidence file: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if data.get("total_commands", 0) < 3:
                errors.append("execution evidence has insufficient commands")

    print(json.dumps({"errors": errors, "score": payload["summary"]["activation_score"]}, indent=2))
    return 1 if errors else 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
