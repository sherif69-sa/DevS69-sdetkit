from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import baseline_hardening as d29


def _evidence_path(root: Path) -> Path:
    return (
        root
        / "docs/artifacts/baseline-hardening-pack/evidence/baseline-hardening-execution-summary.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate baseline-hardening contract.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()

    root = Path(ns.root).resolve()
    payload = d29.build_baseline_hardening_summary(root)

    strict_failures: list[str] = []
    page = root / d29._PAGE_PATH
    page_text = page.read_text(encoding="utf-8") if page.exists() else ""
    for section in [d29._SECTION_HEADER, *d29._REQUIRED_SECTIONS]:
        if section not in page_text:
            strict_failures.append(section)
    for command in d29._REQUIRED_COMMANDS:
        if command not in page_text:
            strict_failures.append(command)

    errors: list[str] = []
    if strict_failures:
        errors.append(f"missing docs contract entries: {strict_failures}")
    if payload["summary"]["critical_failures"]:
        errors.append(f"critical failures: {payload['summary']['critical_failures']}")

    if not ns.skip_evidence:
        evidence = _evidence_path(root)
        if not evidence.exists():
            errors.append(f"missing evidence file: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if data.get("total_commands", 0) < 2:
                errors.append("execution evidence has insufficient commands")

    print(json.dumps({"errors": errors, "score": payload["summary"]["activation_score"]}, indent=2))
    return 1 if errors else 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
