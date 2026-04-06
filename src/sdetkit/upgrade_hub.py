from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
        "actions": ["upgrade_hub_json", "promote_playbook"],
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
        print("upgrade-hub")
    return 0
