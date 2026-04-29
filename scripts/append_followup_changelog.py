from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Append follow-up workflow summary to changelog artifact."
    )
    p.add_argument("--dashboard", default="build/first-proof/dashboard.json")
    p.add_argument("--status-line", default="build/first-proof/upgrade-status-line.txt")
    p.add_argument("--out", default="build/first-proof/followup-changelog.jsonl")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    dashboard = (
        json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
        if Path(args.dashboard).exists()
        else {}
    )
    status_line = (
        Path(args.status_line).read_text(encoding="utf-8").strip()
        if Path(args.status_line).exists()
        else ""
    )

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision": dashboard.get("decision"),
        "health_score": dashboard.get("health_score"),
        "followup_ready": dashboard.get("followup_ready"),
        "status_line": status_line,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    if args.format == "json":
        print(json.dumps(entry, indent=2, sort_keys=True))
    else:
        print(f"followup-changelog: decision={entry['decision']} health={entry['health_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
