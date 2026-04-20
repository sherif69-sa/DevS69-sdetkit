#!/usr/bin/env python3
"""Build a versioned portfolio scorecard from normalized JSON records.

Input can be a JSON array or JSONL with one record per line.
Expected record keys (minimum):
- repo or repo_id
- gate_fast_ok
- gate_release_ok
- doctor_ok
- failed_steps_count

Optional metadata keys:
- team
- lane
- timestamp
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA_NAME = "sdetkit.portfolio.aggregate"


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


def _normalize_repo_row(record: dict[str, Any], *, window_end: str) -> dict[str, Any]:
    repo_id = str(record.get("repo_id") or record.get("repo") or "unknown-repo")
    gate_fast_ok = bool(record.get("gate_fast_ok", False))
    gate_release_ok = bool(record.get("gate_release_ok", False))
    doctor_ok = bool(record.get("doctor_ok", False))
    failed_steps_count = int(record.get("failed_steps_count", 0))

    release_confidence_ok = (
        gate_fast_ok and gate_release_ok and doctor_ok and failed_steps_count == 0
    )

    return {
        "repo_id": repo_id,
        "team": str(record.get("team", "unknown")),
        "lane": str(record.get("lane", "unknown")),
        "risk_tier": _risk(record),
        "release_confidence_ok": release_confidence_ok,
        "gate_fast_ok": gate_fast_ok,
        "gate_release_ok": gate_release_ok,
        "doctor_ok": doctor_ok,
        "failed_steps_count": failed_steps_count,
        "evidence_window_end": window_end,
        "source_timestamp": record.get("timestamp"),
    }


def _build_summary(
    records: list[dict[str, Any]],
    *,
    schema_version: str,
    window_start: str,
    window_end: str,
    generated_at: str,
) -> dict[str, Any]:
    repos = [_normalize_repo_row(record, window_end=window_end) for record in records]
    repos.sort(key=lambda x: (x.get("risk_tier", "unknown"), x.get("repo_id", "")))

    counts = Counter(row["risk_tier"] for row in repos)
    total = len(repos)
    release_gate_failures = sum(1 for row in repos if not row["gate_release_ok"])

    return {
        "schema_name": _SCHEMA_NAME,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "window": {
            "start_date": window_start,
            "end_date": window_end,
        },
        "totals": {
            "repo_count_total": total,
            "repo_count_reporting": total,
            "high_risk_repo_count": counts.get("high", 0),
            "medium_risk_repo_count": counts.get("medium", 0),
            "low_risk_repo_count": counts.get("low", 0),
            "release_gate_failure_rate_percent": round((release_gate_failures / total * 100), 2)
            if total
            else 0.0,
        },
        "repos": repos,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build portfolio release scorecard")
    ap.add_argument("--in", dest="infile", required=True, help="Input file (JSON list or JSONL)")
    ap.add_argument("--out", required=True, help="Output JSON summary path")
    ap.add_argument("--schema-version", default="1.0.0", help="Portfolio aggregate schema version")
    ap.add_argument(
        "--window-start", required=True, help="Reporting window start date (YYYY-MM-DD)"
    )
    ap.add_argument("--window-end", required=True, help="Reporting window end date (YYYY-MM-DD)")
    ap.add_argument(
        "--generated-at", default="", help="Optional generated_at timestamp (ISO-8601 UTC)"
    )
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.out)
    records = _load_records(infile)
    generated_at = args.generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    summary = _build_summary(
        records,
        schema_version=args.schema_version,
        window_start=args.window_start,
        window_end=args.window_end,
        generated_at=generated_at,
    )

    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {outfile} with {summary['totals']['repo_count_total']} repos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
