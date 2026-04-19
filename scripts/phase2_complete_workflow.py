#!/usr/bin/env python3
"""Execute full Phase 2 workflow (startup through wrap handoff)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_step(command: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = "src" if not existing else f"src:{existing}"
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    return {
        "command": " ".join(command),
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def build_summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [step["command"] for step in steps if not step["ok"]]
    return {
        "schema_version": "sdetkit.phase2_complete_workflow.v1",
        "generated_at": _utc_now(),
        "ok": not failed,
        "failed_steps": failed,
        "next_actions": [f"Fix failing step: {cmd}" for cmd in failed],
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full Phase 2 workflow.")
    parser.add_argument("--out-dir", default="build/phase2-complete")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    steps = [
        _run_step(["python", "scripts/phase2_start_workflow.py", "--format", "json"]),
        _run_step(["python", "scripts/check_phase2_start_summary_contract.py", "--format", "json"]),
        _run_step(
            [
                "python",
                "scripts/phase2_status_report.py",
                "--format",
                "json",
                "--out",
                "build/phase2-start/phase2-status.json",
            ]
        ),
        _run_step(
            [
                "python",
                "-m",
                "sdetkit",
                "phase2-hardening-closeout",
                "--emit-pack-dir",
                "docs/artifacts/phase2-hardening-closeout-pack",
                "--execute",
                "--evidence-dir",
                "docs/artifacts/phase2-hardening-closeout-pack/evidence",
                "--format",
                "json",
                "--strict",
            ]
        ),
        _run_step(["python", "scripts/check_phase2_hardening_closeout_contract.py"]),
        _run_step(
            [
                "python",
                "-m",
                "sdetkit",
                "phase2-wrap-handoff-closeout",
                "--emit-pack-dir",
                "docs/artifacts/phase2-wrap-handoff-closeout-pack",
                "--execute",
                "--evidence-dir",
                "docs/artifacts/phase2-wrap-handoff-closeout-pack/evidence",
                "--format",
                "json",
                "--strict",
            ]
        ),
        _run_step(["python", "scripts/check_phase2_wrap_handoff_closeout_contract.py"]),
    ]
    summary = build_summary(steps)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "phase2-complete-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("phase2-complete-workflow: OK" if summary["ok"] else "phase2-complete-workflow: FAIL")
        print(f"- summary: {summary_path}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
