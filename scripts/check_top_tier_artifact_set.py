#!/usr/bin/env python3
"""Check that canonical top-tier artifact set exists for a given date tag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_REQUIRED_PATTERNS = (
    "portfolio-scorecard-sample-{date}.json",
    "kpi-weekly-from-portfolio-{date}.json",
    "kpi-weekly-contract-check-{date}.json",
    "top-tier-contract-check-{date}.json",
    "top-tier-bundle-manifest-{date}.json",
    "top-tier-bundle-manifest-check-{date}.json",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check top-tier artifact set for date tag")
    ap.add_argument("--date-tag", required=True)
    ap.add_argument("--artifacts-dir", default="docs/artifacts")
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    missing: list[str] = []
    found: list[str] = []
    invalid_json: list[str] = []
    invalid_json_errors: list[dict[str, str]] = []

    for pattern in _REQUIRED_PATTERNS:
        rel = pattern.format(date=args.date_tag)
        path = artifacts_dir / rel
        if path.is_file():
            found.append(str(path))
            try:
                json.loads(path.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
                invalid_json.append(str(path))
                invalid_json_errors.append({"path": str(path), "error": str(exc)})
        else:
            missing.append(str(path))

    report = {
        "ok": not missing and not invalid_json,
        "date_tag": args.date_tag,
        "artifacts_dir": str(artifacts_dir),
        "required": [
            str(artifacts_dir / pattern.format(date=args.date_tag))
            for pattern in _REQUIRED_PATTERNS
        ],
        "required_count": len(_REQUIRED_PATTERNS),
        "found_count": len(found),
        "missing_count": len(missing),
        "invalid_json_count": len(invalid_json),
        "found": found,
        "missing": missing,
        "invalid_json": invalid_json,
        "invalid_json_errors": invalid_json_errors,
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report))
    return 0 if (not missing and not invalid_json) else 1


if __name__ == "__main__":
    raise SystemExit(main())
