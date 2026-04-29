from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Track first-proof ops bundle contract trend over time.")
    p.add_argument("--contract", default="build/first-proof/ops-bundle-contract.json")
    p.add_argument("--history", default="build/first-proof/ops-bundle-contract-history.jsonl")
    p.add_argument("--out", default="build/first-proof/ops-bundle-contract-trend.json")
    p.add_argument("--window", type=int, default=10)
    p.add_argument("--branch", default="local")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": bool(contract.get("ok", False)),
        "missing_count": len(contract.get("missing") or []),
        "branch": args.branch,
    }

    hist_path = Path(args.history)
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    with hist_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    rows = []
    for raw in hist_path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    recent = rows[-args.window :]
    total = len(recent)
    passes = sum(1 for r in recent if r.get("ok"))
    pass_rate = (passes / total) if total else 0.0

    branch_rows = [r for r in rows if str(r.get("branch", "")) == args.branch]
    branch_recent = branch_rows[-args.window :]
    branch_total = len(branch_recent)
    branch_passes = sum(1 for r in branch_recent if r.get("ok"))
    branch_pass_rate = (branch_passes / branch_total) if branch_total else 0.0
    payload = {
        "schema_version": "1.0.0",
        "ok": pass_rate >= 0.8,
        "window": args.window,
        "recent_runs": total,
        "recent_passes": passes,
        "recent_pass_rate": round(pass_rate, 4),
        "latest": entry,
        "branch": args.branch,
        "branch_recent_runs": branch_total,
        "branch_recent_passes": branch_passes,
        "branch_recent_pass_rate": round(branch_pass_rate, 4),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"ops-bundle-trend: pass_rate={payload['recent_pass_rate']:.2f} window={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
