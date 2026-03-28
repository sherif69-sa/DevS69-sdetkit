from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def run_cycle_contract_check(cycle: int, root: str = ".", skip_evidence: bool = False) -> int:
    repo_root = Path(root).resolve()
    module = importlib.import_module(f"sdetkit.continuous_upgrade_cycle{cycle}_closeout")
    build = getattr(module, f"build_continuous_upgrade_cycle{cycle}_closeout_summary")
    payload = build(repo_root)

    errors: list[str] = []
    if not payload.get("summary", {}).get("strict_pass", False):
        errors.append("summary.strict_pass is false")
    if payload.get("summary", {}).get("activation_score", 0) < 95:
        errors.append("activation_score below 95")
    if payload.get("summary", {}).get("critical_failures"):
        errors.append("critical_failures is not empty")

    if not skip_evidence:
        evidence = (
            repo_root
            / f"docs/artifacts/continuous-upgrade-cycle{cycle}-closeout-pack/evidence/cycle{cycle}-execution-summary.json"
        )
        if not evidence.exists():
            errors.append(f"missing evidence summary: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if int(data.get("total_commands", 0)) < 3:
                errors.append("evidence total_commands below 3")

    command = f"continuous-upgrade-cycle{cycle}"
    if errors:
        print(f"{command} contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"{command} contract check passed")
    return 0
