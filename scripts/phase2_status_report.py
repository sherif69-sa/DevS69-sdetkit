#!/usr/bin/env python3
"""Build a Phase 2 workflow status report from emitted artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_SUMMARY_SCHEMA = "sdetkit.phase2_start_workflow.v1"
REQUIRED_KICKOFF_ARTIFACTS = (
    "phase2-kickoff-summary.json",
    "phase2-kickoff-summary.md",
    "phase2-kickoff-delivery-board.md",
    "phase2-kickoff-validation-commands.md",
    "evidence/phase2-kickoff-execution-summary.json",
)


def build_status(summary_path: Path, kickoff_pack_dir: Path) -> dict[str, Any]:
    blockers: list[str] = []
    accomplished: list[str] = []
    not_yet: list[str] = []

    if summary_path.is_file():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == EXPECTED_SUMMARY_SCHEMA:
            accomplished.append(f"summary_schema::{EXPECTED_SUMMARY_SCHEMA}")
        else:
            blockers.append("summary_schema_mismatch")
            not_yet.append(f"summary_schema::{EXPECTED_SUMMARY_SCHEMA}")
        if bool(payload.get("ok", False)):
            accomplished.append("summary_ok")
        else:
            blockers.append("summary_ok_false")
            not_yet.append("summary_ok")
    else:
        blockers.append(f"missing_summary::{summary_path}")
        not_yet.append(f"summary_exists::{summary_path}")

    for rel in REQUIRED_KICKOFF_ARTIFACTS:
        path = kickoff_pack_dir / rel
        if path.is_file():
            accomplished.append(f"kickoff_artifact::{rel}")
        else:
            not_yet.append(f"kickoff_artifact::{rel}")
            blockers.append(f"missing_kickoff_artifact::{rel}")

    return {
        "schema_version": "sdetkit.phase2_status.v1",
        "ok": len(blockers) == 0,
        "accomplished": accomplished,
        "not_yet": not_yet,
        "hard_blockers": blockers,
        "summary": str(summary_path),
        "kickoff_pack_dir": str(kickoff_pack_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 2 status report.")
    parser.add_argument("--summary", default="build/phase2-start/phase2-start-summary.json")
    parser.add_argument("--kickoff-pack-dir", default="docs/artifacts/phase2-kickoff-pack")
    parser.add_argument("--out", default="build/phase2-start/phase2-status.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    status = build_status(Path(args.summary), Path(args.kickoff_pack_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print("phase2-status: COMPLETE" if status["ok"] else "phase2-status: INCOMPLETE")
        print(f"- out: {out_path}")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
