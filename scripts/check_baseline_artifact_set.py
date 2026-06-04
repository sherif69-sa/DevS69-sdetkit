#!/usr/bin/env python3
"""Validate that required baseline artifact set exists and is readable JSON/Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_JSON = [
    "build/baseline/baseline-status.json",
    "build/baseline/baseline-next-actions.json",
    "build/baseline/baseline-ops-snapshot.json",
    "build/baseline/baseline-completion-dashboard.json",
    "build/baseline/weekly-pack/baseline-weekly-pack.json",
    "build/baseline/baseline-control-loop-report.json",
    "build/baseline/baseline-run-all.json",
    "build/baseline/baseline-telemetry-summary.json",
]

REQUIRED_MD = [
    "build/baseline/baseline-ops-snapshot.md",
    "build/baseline/baseline-completion-dashboard.md",
    "build/baseline/weekly-pack/baseline-weekly-pack.md",
    "build/baseline/baseline-control-loop-report.md",
    "build/baseline/baseline-run-all.md",
]


def _validate_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate baseline artifact set.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    rows = []
    for rel in REQUIRED_JSON:
        p = Path(rel)
        rows.append(
            {
                "path": rel,
                "kind": "json",
                "exists": p.is_file(),
                "valid": p.is_file() and _validate_json(p),
            }
        )
    for rel in REQUIRED_MD:
        p = Path(rel)
        rows.append(
            {
                "path": rel,
                "kind": "markdown",
                "exists": p.is_file(),
                "valid": p.is_file(),
            }
        )

    missing = [row["path"] for row in rows if not row["exists"]]
    invalid = [row["path"] for row in rows if row["exists"] and not row["valid"]]
    ok = not missing and not invalid

    payload = {
        "ok": ok,
        "schema_version": "sdetkit.baseline_artifact_set_contract.v1",
        "missing": missing,
        "invalid": invalid,
        "checks": rows,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("baseline-artifact-set: OK" if ok else "baseline-artifact-set: FAIL")
        for item in missing:
            print(f"- missing: {item}")
        for item in invalid:
            print(f"- invalid: {item}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
