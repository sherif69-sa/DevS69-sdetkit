#!/usr/bin/env python3
"""Build a portfolio scorecard from normalized JSON records.

Input can be a JSON array or JSONL with one record per line.
Expected record keys:
- repo
- team
- lane
- gate_fast_ok
- gate_release_ok
- doctor_ok
- failed_steps_count
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text().strip()
    if not text:
        return []

    # JSON array mode
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        if isinstance(parsed, list):
            return [dict(item) for item in parsed]
        raise ValueError("JSON input must be a list of records (or JSONL)")

    # JSONL mode
    records = []
    for line in text.splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _risk(record: dict[str, Any]) -> str:
    gate_release_ok = bool(record.get("gate_release_ok", False))
    gate_fast_ok = bool(record.get("gate_fast_ok", False))
    doctor_ok = bool(record.get("doctor_ok", False))
    failed_steps = int(record.get("failed_steps_count", 0))

    if gate_fast_ok and gate_release_ok and doctor_ok and failed_steps == 0:
        return "low"
    if not gate_release_ok or failed_steps >= 2:
        return "high"
    return "medium"


def _build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = []
    for r in records:
        row = dict(r)
        row["risk_level"] = _risk(r)
        enriched.append(row)

    counts = Counter(row["risk_level"] for row in enriched)
    total = len(enriched)
    release_gate_failures = sum(1 for row in enriched if not bool(row.get("gate_release_ok", False)))

    return {
        "total_repos": total,
        "risk_counts": dict(counts),
        "pct_low_risk": round((counts.get("low", 0) / total * 100), 2) if total else 0.0,
        "pct_release_gate_failure": round((release_gate_failures / total * 100), 2) if total else 0.0,
        "repos": sorted(enriched, key=lambda x: (x.get("risk_level", "unknown"), x.get("repo", ""))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build portfolio release scorecard")
    ap.add_argument("--in", dest="infile", required=True, help="Input file (JSON list or JSONL)")
    ap.add_argument("--out", required=True, help="Output JSON summary path")
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.out)
    records = _load_records(infile)
    summary = _build_summary(records)

    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {outfile} with {summary['total_repos']} repos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
