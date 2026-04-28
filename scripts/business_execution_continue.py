#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.business-execution-continue.v1"


def build_continue_payload(followup: dict[str, Any]) -> dict[str, Any]:
    checkpoint_status = str(followup.get("checkpoint_status", "on-track"))
    keep_moving = bool(followup.get("keep_moving", True))
    recommended = str(followup.get("recommended_command", "make business-execution-pipeline"))
    checkpoint_command = str(followup.get("checkpoint_command", "make business-execution-followup"))

    if checkpoint_status == "due":
        selected_command = checkpoint_command
        reason = "Checkpoint is due now; run checkpoint command immediately."
        should_run_now = True
    elif keep_moving:
        selected_command = recommended
        reason = "Execution should keep moving; run recommended command."
        should_run_now = True
    else:
        selected_command = checkpoint_command
        reason = "No immediate movement required; keep checkpoint command ready."
        should_run_now = False

    return {
        "schema_version": SCHEMA_VERSION,
        "checkpoint_status": checkpoint_status,
        "keep_moving": keep_moving,
        "selected_command": selected_command,
        "reason": reason,
        "should_run_now": should_run_now,
    }


def render_continue_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Business Execution Continue Command",
            "",
            f"- Checkpoint status: {payload.get('checkpoint_status')}",
            f"- Keep moving: {payload.get('keep_moving')}",
            f"- Should run now: {payload.get('should_run_now')}",
            f"- Reason: {payload.get('reason')}",
            "",
            "## Selected command",
            f"`{payload.get('selected_command')}`",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the next execution command from follow-up artifact.")
    parser.add_argument("--followup", default="build/business-execution/business-execution-followup.json")
    parser.add_argument("--out-json", default="build/business-execution/business-execution-continue.json")
    parser.add_argument("--out-md", default="build/business-execution/business-execution-continue.md")
    args = parser.parse_args(argv)

    followup = json.loads(Path(args.followup).read_text(encoding="utf-8"))
    payload = build_continue_payload(followup)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_continue_md(payload), encoding="utf-8")

    print(f"business-execution-continue: wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
