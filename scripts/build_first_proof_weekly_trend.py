from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _adaptive_confidence(adaptive_postcheck: dict[str, Any] | None) -> int | None:
    if not isinstance(adaptive_postcheck, dict):
        return None
    summary = adaptive_postcheck.get("summary", {})
    if not isinstance(summary, dict):
        return None
    value = summary.get("confidence_score")
    return int(value) if isinstance(value, (int, float)) else None


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    recent = payload.get("recent_runs", [])
    lines = ["# First-Proof Weekly Trend", ""]
    lines.append(f"- Generated at: `{payload.get('generated_at', 'unknown')}`")
    lines.append(f"- Total tracked runs: `{int(summary.get('total_runs', 0))}`")
    lines.append(f"- Last-7 ship rate: `{float(summary.get('ship_rate_last_7', 0.0)):.2f}`")
    if summary.get("adaptive_confidence") is not None:
        lines.append(f"- Adaptive confidence score: `{int(summary['adaptive_confidence'])}`")
    lines.append("")
    lines.append("## Recent Runs")
    if isinstance(recent, list) and recent:
        for row in recent:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- `{row.get('captured_at', 'unknown')}` decision=`{row.get('decision', 'unknown')}` failed_steps=`{','.join(row.get('failed_steps', []))}`"
            )
    else:
        lines.append("- No run history yet.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build first-proof weekly trend summary.")
    parser.add_argument(
        "--db", type=Path, default=Path("build/first-proof/first-proof-learning-db.jsonl")
    )
    parser.add_argument(
        "--adaptive-postcheck",
        type=Path,
        default=Path("build/adaptive-postcheck-min.json"),
    )
    parser.add_argument(
        "--out-json", type=Path, default=Path("build/first-proof/weekly-trend.json")
    )
    parser.add_argument("--out-md", type=Path, default=Path("build/first-proof/weekly-trend.md"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    rows = _load_jsonl(args.db)
    recent = rows[-7:]
    ship_last_7 = sum(1 for row in recent if row.get("decision") == "SHIP")
    ship_rate_last_7 = (ship_last_7 / len(recent)) if recent else 0.0
    adaptive_payload = _read_json(args.adaptive_postcheck)

    payload = {
        "schema_version": "sdetkit.first-proof-weekly-trend.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_runs": len(rows),
            "ship_rate_last_7": ship_rate_last_7,
            "adaptive_confidence": _adaptive_confidence(adaptive_payload),
        },
        "recent_runs": recent,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_md.write_text(_render_md(payload), encoding="utf-8")

    result = {
        "ok": True,
        "out_json": str(args.out_json),
        "out_md": str(args.out_md),
        "total_runs": len(rows),
        "ship_rate_last_7": ship_rate_last_7,
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"weekly trend json: {args.out_json}")
        print(f"weekly trend md: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
