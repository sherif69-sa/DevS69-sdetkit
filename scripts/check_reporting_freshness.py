#!/usr/bin/env python3
"""Check freshness of canonical top-tier reporting artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


_REQUIRED_PATTERNS = (
    "portfolio-scorecard-sample-{date}.json",
    "kpi-weekly-from-portfolio-{date}.json",
    "kpi-weekly-contract-check-{date}.json",
    "top-tier-contract-check-{date}.json",
    "top-tier-bundle-manifest-{date}.json",
    "top-tier-bundle-manifest-check-{date}.json",
    "top-tier-artifact-set-check-{date}.json",
)


def _parse_date(date_text: str) -> datetime:
    return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check reporting artifact freshness")
    ap.add_argument("--date-tag", required=True, help="Date tag in YYYY-MM-DD format")
    ap.add_argument("--artifacts-dir", default="docs/artifacts")
    ap.add_argument("--max-age-days", type=int, default=7)
    ap.add_argument(
        "--reference-date",
        default="",
        help="Optional YYYY-MM-DD date used as freshness reference (defaults to current UTC date)",
    )
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    args = ap.parse_args()

    reference = _parse_date(args.reference_date) if args.reference_date else datetime.now(timezone.utc)
    artifacts_dir = Path(args.artifacts_dir)

    missing: list[str] = []
    stale: list[dict[str, object]] = []
    checked: list[dict[str, object]] = []

    for pattern in _REQUIRED_PATTERNS:
        rel = pattern.format(date=args.date_tag)
        path = artifacts_dir / rel
        if not path.is_file():
            missing.append(str(path))
            continue

        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_days = int((reference.date() - mtime.date()).days)
        entry = {"path": str(path), "mtime": mtime.date().isoformat(), "age_days": age_days}
        checked.append(entry)
        if age_days > args.max_age_days:
            stale.append(entry)

    report = {
        "ok": not missing and not stale,
        "date_tag": args.date_tag,
        "artifacts_dir": str(artifacts_dir),
        "reference_date": reference.date().isoformat(),
        "max_age_days": args.max_age_days,
        "required_count": len(_REQUIRED_PATTERNS),
        "checked_count": len(checked),
        "missing_count": len(missing),
        "stale_count": len(stale),
        "checked": checked,
        "missing": missing,
        "stale": stale,
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
