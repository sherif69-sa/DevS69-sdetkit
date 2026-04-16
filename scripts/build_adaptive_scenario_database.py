#!/usr/bin/env python3
"""Build adaptive scenario database from repository test surfaces."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def _domain_for_path(path: Path) -> str:
    p = path.as_posix()
    if "security" in p:
        return "security"
    if "release" in p or "version" in p:
        return "release"
    if "repo" in p or "policy" in p:
        return "governance"
    if "review" in p or "doctor" in p:
        return "reliability"
    return "quality"


def build_db(repo_root: Path) -> dict:
    tests_root = repo_root / "tests"
    scenario_entries: list[dict] = []
    domain_counts: Counter[str] = Counter()

    for file in sorted(tests_root.rglob("test_*.py")):
        text = file.read_text(encoding="utf-8", errors="ignore")
        funcs = re.findall(r"^def\s+(test_[\w_]+)", text, flags=re.M)
        domain = _domain_for_path(file)
        for fn in funcs:
            scenario_id = f"{file.as_posix()}::{fn}"
            scenario_entries.append(
                {
                    "scenario_id": scenario_id,
                    "domain": domain,
                    "source": file.as_posix(),
                    "status": "active",
                }
            )
            domain_counts[domain] += 1

    payload = {
        "schema_version": "sdetkit.adaptive-scenario-database.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scenarios": len(scenario_entries),
            "domains": dict(sorted(domain_counts.items())),
            "target_minimum": 500,
            "meets_target": len(scenario_entries) >= 500,
        },
        "scenarios": scenario_entries,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo_root = Path(args.repo).resolve()
    payload = build_db(repo_root)
    if args.out:
        out = Path(args.out)
    else:
        date_tag = datetime.now(timezone.utc).date().isoformat()
        out = repo_root / "docs/artifacts" / f"adaptive-scenario-database-{date_tag}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
