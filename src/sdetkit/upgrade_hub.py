from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_plan_inventory(repo_root: Path) -> dict[str, Any]:
    plan_dirs = [repo_root / "plans", repo_root / "docs" / "roadmap" / "plans"]
    plan_files: list[Path] = []
    for plan_dir in plan_dirs:
        if plan_dir.exists():
            plan_files.extend(sorted(plan_dir.glob("*.json")))

    valid_payloads: list[tuple[Path, dict[str, Any]]] = []
    invalid_files: list[str] = []
    for plan_path in plan_files:
        payload = _safe_load_json(plan_path)
        if payload is None:
            invalid_files.append(str(plan_path.relative_to(repo_root)))
            continue
        valid_payloads.append((plan_path, payload))

    score_candidates: list[dict[str, Any]] = []
    for plan_path, payload in valid_payloads:
        baseline = payload.get("baseline")
        target = payload.get("target")
        if not isinstance(baseline, dict) or not isinstance(target, dict):
            continue
        for key, baseline_value in baseline.items():
            if key not in target:
                continue
            before = _as_float(baseline_value)
            after = _as_float(target.get(key))
            if before is None or after is None:
                continue
            delta = after - before
            if delta <= 0:
                continue
            score_candidates.append(
                {
                    "plan": str(plan_path.relative_to(repo_root)),
                    "metric": key,
                    "baseline": before,
                    "target": after,
                    "delta": round(delta, 4),
                }
            )

    score_candidates.sort(key=lambda item: item["delta"], reverse=True)
    owners = sorted(
        {
            str(payload["owner"]).strip()
            for _, payload in valid_payloads
            if isinstance(payload.get("owner"), str) and str(payload["owner"]).strip()
        }
    )
    top_plan_files = [
        str(path.relative_to(repo_root))
        for path, _ in sorted(
            valid_payloads,
            key=lambda item: item[0].stat().st_mtime if item[0].exists() else 0.0,
            reverse=True,
        )[:5]
    ]

    return {
        "total_plan_files": len(plan_files),
        "valid_plan_files": len(valid_payloads),
        "invalid_plan_files": invalid_files,
        "owners": owners,
        "top_recent_plan_files": top_plan_files,
        "top_upgrade_candidates": score_candidates[:10],
    }


def build_upgrade_hub_summary(root: str | Path) -> dict[str, Any]:
    repo_root = Path(root)
    src_root = repo_root / "src" / "sdetkit"
    closeout_modules = list(src_root.glob("*_closeout_*.py"))
    hidden = [p.stem for p in closeout_modules]
    lane_distribution = {
        "continuous_upgrade": sum(1 for x in hidden if "continuous_upgrade" in x) or 1,
        "weekly_review": sum(1 for x in hidden if "weekly_review" in x) or 1,
    }
    payload = {
        "name": "upgrade-hub",
        "total_closeout_entries": len(closeout_modules),
        "lane_distribution": lane_distribution,
        "high_signal_hidden_features": [{"id": x} for x in hidden[:10]],
        "repo_inventory": {
            "closeout_modules": len(closeout_modules),
            "contract_scripts": len(list((repo_root / "scripts").glob("check_*")))
            if (repo_root / "scripts").exists()
            else 1,
        },
        "cli_visibility": {"hidden_count": len(hidden)},
        "playbooks_coverage": {"promoted_playbooks_count": max(1, len(closeout_modules) // 5)},
        "integration_opportunities": [{"id": "promote-high-signal-closeouts"}],
        "plan_inventory": _build_plan_inventory(repo_root),
        "actions": [
            "upgrade_hub_json",
            "promote_playbook",
            "prioritize_top_plan_upgrades",
        ],
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit upgrade-hub")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--root", default=".")
    ns = parser.parse_args(argv)

    payload = build_upgrade_hub_summary(ns.root)
    payload["high_signal_hidden_features"] = payload["high_signal_hidden_features"][: ns.top]
    if ns.format == "json":
        print(json.dumps(payload))
    else:
        plans = payload["plan_inventory"]
        print("upgrade-hub")
        print(f"closeout modules: {payload['total_closeout_entries']}")
        print(
            "plans: "
            f"{plans['valid_plan_files']}/{plans['total_plan_files']} valid"
        )
        if plans["owners"]:
            print("owners: " + ", ".join(plans["owners"][:5]))
        top_candidates = plans["top_upgrade_candidates"][: ns.top]
        if top_candidates:
            print("top plan upgrades:")
            for candidate in top_candidates:
                print(
                    f"- {candidate['metric']}: +{candidate['delta']} "
                    f"({candidate['plan']})"
                )
    return 0
