#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from powerfuel_common import dump_json

TRIGGERS = ("push", "pull_request", "workflow_dispatch", "schedule", "release")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build powerfuel baseline metrics from repository artifacts")
    p.add_argument("--workflows-dir", default=".github/workflows")
    p.add_argument("--first-proof-summary", default="build/first-proof/first-proof-summary.json")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--out", default=None)
    p.add_argument("--generated-at", default=None, help="ISO timestamp override for deterministic outputs")
    return p.parse_args()


def detect_triggers(text: str) -> list[str]:
    found: list[str] = []
    for trigger in TRIGGERS:
        if re.search(rf"(?m)^\s*{re.escape(trigger)}\s*:\s*", text):
            found.append(trigger)
    return found


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    args = parse_args()
    workflows_dir = Path(args.workflows_dir)
    first_proof_path = Path(args.first_proof_summary)

    workflow_files = sorted(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml")))
    trigger_counter: Counter[str] = Counter()
    workflow_trigger_map: dict[str, list[str]] = {}
    for wf in workflow_files:
        text = wf.read_text(encoding="utf-8", errors="ignore")
        triggers = detect_triggers(text)
        workflow_trigger_map[wf.name] = triggers
        trigger_counter.update(triggers)

    duplicate_trigger_paths = sum(max(0, count - 1) for count in trigger_counter.values())

    first_proof = load_json(first_proof_path)
    first_proof_success_rate = None
    time_to_first_proof_median_minutes = None
    if first_proof:
        decision = str(first_proof.get("decision", "")).upper()
        first_proof_success_rate = 1.0 if decision == "SHIP" else 0.0 if decision else None
        duration_seconds = first_proof.get("duration_seconds")
        if isinstance(duration_seconds, (int, float)) and duration_seconds >= 0:
            time_to_first_proof_median_minutes = round(duration_seconds / 60.0, 2)

    payload = {
        "date": args.date_tag,
        "status": "baseline-measured",
        "generated_at": args.generated_at or datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "workflows_dir": str(workflows_dir),
            "workflow_files": len(workflow_files),
            "first_proof_summary": str(first_proof_path),
        },
        "kpis": {
            "workflow_count": len(workflow_files),
            "duplicate_trigger_paths": duplicate_trigger_paths,
            "ci_minutes_per_merged_pr": None,
            "first_proof_success_rate": first_proof_success_rate,
            "time_to_first_proof_median_minutes": time_to_first_proof_median_minutes,
            "strict_finding_remediation_lead_time_hours": None,
            "decision_reproducibility_rate": None,
        },
        "trigger_counts": dict(trigger_counter),
        "workflow_trigger_map": workflow_trigger_map,
        "notes": [
            "CI-minute and remediation KPIs require CI telemetry/history and remain null until wired.",
            "Duplicate trigger paths are estimated from top-level trigger key occurrences in workflow YAML files.",
        ],
    }

    default_out = f"docs/artifacts/powerfuel-baseline-{args.date_tag}.json"
    out = Path(args.out or default_out)
    dump_json(out, payload)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
