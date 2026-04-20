#!/usr/bin/env python3
"""Build a single weekly Phase 1 report pack from generated artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARTIFACT_INPUTS = {
    "status": "build/phase1-baseline/phase1-status.json",
    "next_actions": "build/phase1-baseline/phase1-next-actions.json",
    "ops_snapshot": "build/phase1-baseline/phase1-ops-snapshot.json",
    "completion_dashboard": "build/phase1-baseline/phase1-completion-dashboard.json",
    "baseline_summary": "build/phase1-baseline/phase1-baseline-summary.json",
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_pack_payload(inputs: dict[str, Path]) -> dict[str, Any]:
    loaded = {name: _load_json(path) for name, path in inputs.items()}
    ready = bool(loaded.get("completion_dashboard", {}).get("ready_to_close", False))
    hard_blockers = loaded.get("status", {}).get("hard_blockers", [])
    if not isinstance(hard_blockers, list):
        hard_blockers = []

    return {
        "schema_version": "sdetkit.phase1_weekly_report_pack.v1",
        "generated_at": _utc_now(),
        "phase": "phase1",
        "ready_to_close": ready,
        "hard_blocker_count": len(hard_blockers),
        "artifact_inventory": {
            name: {
                "path": str(path),
                "exists": path.is_file(),
            }
            for name, path in inputs.items()
        },
        "top_risk_item": loaded.get("ops_snapshot", {}).get("top_risk_item"),
        "next_step": loaded.get("completion_dashboard", {}).get("next_step", "make phase1-next"),
        "hard_blockers": hard_blockers,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 weekly report pack",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Ready to close: {payload.get('ready_to_close', False)}",
        f"- Hard blocker count: {payload.get('hard_blocker_count', 0)}",
        f"- Next step: {payload.get('next_step', '')}",
        "",
        "## Artifact inventory",
    ]

    inventory = payload.get("artifact_inventory", {})
    if isinstance(inventory, dict):
        for name, meta in inventory.items():
            if isinstance(meta, dict):
                lines.append(
                    f"- {name}: exists={meta.get('exists', False)} path={meta.get('path', '')}"
                )

    lines.extend(["", "## Hard blockers"])
    blockers = payload.get("hard_blockers", [])
    if isinstance(blockers, list) and blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 1 weekly report pack.")
    parser.add_argument("--out-dir", default="build/phase1-baseline/weekly-pack")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = {name: Path(path) for name, path in ARTIFACT_INPUTS.items()}
    payload = build_pack_payload(inputs)

    out_json = out_dir / "phase1-weekly-pack.json"
    out_md = out_dir / "phase1-weekly-pack.md"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(payload), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-weekly-pack: OK")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
