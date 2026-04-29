from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


REQUIRED = [
    "first-proof-summary.json",
    "health-score.json",
    "doctor-remediate.json",
    "first-proof-learning-rollup.json",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Check first-proof artifact freshness and completeness.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--max-age-hours", type=int, default=48)
    p.add_argument("--out", default="build/first-proof/artifact-freshness.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    now = time.time()
    max_age_seconds = args.max_age_hours * 3600

    checks = []
    for name in REQUIRED:
        path = root / name
        exists = path.exists()
        age_seconds = None
        fresh = False
        if exists:
            age_seconds = max(0.0, now - path.stat().st_mtime)
            fresh = age_seconds <= max_age_seconds
        checks.append({"artifact": name, "exists": exists, "fresh": fresh, "age_seconds": age_seconds})

    missing = [c["artifact"] for c in checks if not c["exists"]]
    stale = [c["artifact"] for c in checks if c["exists"] and not c["fresh"]]
    ok = not missing and not stale
    payload = {
        "ok": ok,
        "artifact_dir": str(root),
        "max_age_hours": args.max_age_hours,
        "missing": missing,
        "stale": stale,
        "checks": checks,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"artifact-freshness: ok={ok} missing={len(missing)} stale={len(stale)}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
