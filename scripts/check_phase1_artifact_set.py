#!/usr/bin/env python3
"""Validate that required Phase 1 artifact set exists and is readable JSON/Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_JSON = [
    "build/phase1-baseline/phase1-status.json",
    "build/phase1-baseline/phase1-next-actions.json",
    "build/phase1-baseline/phase1-ops-snapshot.json",
    "build/phase1-baseline/phase1-completion-dashboard.json",
    "build/phase1-baseline/weekly-pack/phase1-weekly-pack.json",
    "build/phase1-baseline/phase1-control-loop-report.json",
    "build/phase1-baseline/phase1-run-all.json",
    "build/phase1-baseline/phase1-telemetry-summary.json",
]

REQUIRED_MD = [
    "build/phase1-baseline/phase1-ops-snapshot.md",
    "build/phase1-baseline/phase1-completion-dashboard.md",
    "build/phase1-baseline/weekly-pack/phase1-weekly-pack.md",
    "build/phase1-baseline/phase1-control-loop-report.md",
    "build/phase1-baseline/phase1-run-all.md",
]


def _validate_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 1 artifact set.")
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
        "schema_version": "sdetkit.phase1_artifact_set_contract.v1",
        "missing": missing,
        "invalid": invalid,
        "checks": rows,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-artifact-set: OK" if ok else "phase1-artifact-set: FAIL")
        for item in missing:
            print(f"- missing: {item}")
        for item in invalid:
            print(f"- invalid: {item}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
