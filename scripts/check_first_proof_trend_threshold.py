from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("weekly trend payload must be a JSON object")
    return payload


def _load_profile(
    *,
    profile_config: Path | None,
    branch: str,
) -> dict[str, Any]:
    if profile_config is None or not profile_config.is_file():
        return {}
    payload = _read_json(profile_config)
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, dict):
        return {}
    selected = profiles.get(branch)
    if not isinstance(selected, dict):
        selected = profiles.get("default")
    return selected if isinstance(selected, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate first-proof weekly trend thresholds.")
    parser.add_argument("--trend", type=Path, default=Path("build/first-proof/weekly-trend.json"))
    parser.add_argument("--min-ship-rate", type=float, default=0.5)
    parser.add_argument("--min-total-runs", type=int, default=3)
    parser.add_argument("--min-consecutive-breaches", type=int, default=2)
    parser.add_argument(
        "--branch", default=None, help="Branch/profile name for threshold overrides."
    )
    parser.add_argument(
        "--profile-config",
        type=Path,
        default=None,
        help="Optional threshold profile config JSON.",
    )
    parser.add_argument("--fail-on-breach", action="store_true")
    parser.add_argument(
        "--out", type=Path, default=Path("build/first-proof/weekly-threshold-check.json")
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    branch = args.branch or os.environ.get("GITHUB_REF_NAME", "local")
    profile = _load_profile(profile_config=args.profile_config, branch=branch)
    min_ship_rate = float(profile.get("min_ship_rate", args.min_ship_rate))
    min_total_runs = int(profile.get("min_total_runs", args.min_total_runs))
    min_consecutive = int(profile.get("min_consecutive_breaches", args.min_consecutive_breaches))
    fail_on_breach = bool(profile.get("fail_on_breach", args.fail_on_breach))

    payload = _read_json(args.trend)
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    ship_rate = float(summary.get("ship_rate_last_7", 0.0)) if isinstance(summary, dict) else 0.0
    total_runs = int(summary.get("total_runs", 0)) if isinstance(summary, dict) else 0
    recent_runs = payload.get("recent_runs", []) if isinstance(payload, dict) else []
    consecutive_no_ship = 0
    if isinstance(recent_runs, list):
        for row in reversed(recent_runs):
            if not isinstance(row, dict):
                continue
            if row.get("decision") == "NO-SHIP":
                consecutive_no_ship += 1
            else:
                break

    enough_data = total_runs >= min_total_runs
    rate_ok = ship_rate >= min_ship_rate
    consecutive_breach = consecutive_no_ship >= min_consecutive
    breach = enough_data and (not rate_ok) and consecutive_breach

    result = {
        "ok": not breach,
        "breach": breach,
        "enough_data": enough_data,
        "ship_rate_last_7": ship_rate,
        "total_runs": total_runs,
        "branch": branch,
        "min_ship_rate": min_ship_rate,
        "min_total_runs": min_total_runs,
        "min_consecutive_breaches": min_consecutive,
        "consecutive_no_ship": consecutive_no_ship,
        "fail_on_breach": fail_on_breach,
        "action": (
            "recover-first-proof-ship-rate"
            if breach
            else (
                "collect-more-data"
                if not enough_data
                else (
                    "watch-consecutive-no-ship"
                    if not consecutive_breach
                    else "maintain-current-lane"
                )
            )
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        state = "breach" if breach else "ok"
        print(f"first-proof trend threshold: {state}")

    if fail_on_breach and breach:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
