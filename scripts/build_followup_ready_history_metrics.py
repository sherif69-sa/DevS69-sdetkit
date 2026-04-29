from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Track follow-up readiness history and remediation time metrics."
    )
    p.add_argument("--followup", default="build/first-proof/followup-ready.json")
    p.add_argument("--history", default="build/first-proof/followup-ready-history.jsonl")
    p.add_argument("--out", default="build/first-proof/followup-ready-metrics.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    followup = json.loads(Path(args.followup).read_text(encoding="utf-8"))
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "ok": bool(followup.get("ok", False))}

    hist_path = Path(args.history)
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    with hist_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    rows = [
        json.loads(line)
        for line in hist_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # remediation duration: time from a failed run to next successful run
    durations_hours: list[float] = []
    open_failure_ts: datetime | None = None
    for row in rows:
        ts = _parse_ts(row["ts"])
        ok = bool(row.get("ok", False))
        if not ok and open_failure_ts is None:
            open_failure_ts = ts
        elif ok and open_failure_ts is not None:
            durations_hours.append((ts - open_failure_ts).total_seconds() / 3600.0)
            open_failure_ts = None

    payload = {
        "ok": True,
        "history_runs": len(rows),
        "recent_ok": entry["ok"],
        "median_time_to_remediate_hours": round(median(durations_hours), 4)
        if durations_hours
        else None,
        "closed_incidents": len(durations_hours),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "followup-ready-metrics: "
            f"runs={payload['history_runs']} median_hours={payload['median_time_to_remediate_hours']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
