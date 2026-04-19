#!/usr/bin/env python3
"""Execute Phase 2 startup workflow and emit an operational summary."""

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
    next_actions = [f"Fix failing step: {cmd}" for cmd in failed]
    return {
        "schema_version": "sdetkit.phase2_start_workflow.v1",
        "generated_at": _utc_now(),
        "ok": not failed,
        "failed_steps": failed,
        "next_actions": next_actions,
        "steps": steps,
    }


def _to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 startup workflow summary",
        "",
        f"- Generated at: {summary.get('generated_at', '')}",
        f"- OK: {summary.get('ok', False)}",
        "",
        "## Steps",
    ]
    for step in summary.get("steps", []):
        lines.append(f"- {'OK' if step['ok'] else 'FAIL'}: `{step['command']}`")
    lines.extend(["", "## Next actions"])
    actions = summary.get("next_actions", [])
    if actions:
        lines.extend([f"- {item}" for item in actions])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 startup workflow.")
    parser.add_argument("--out-dir", default="build/phase2-start")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        _run_step(["python", "scripts/phase2_seed_prerequisites.py"]),
        _run_step(
            [
                "python",
                "-m",
                "sdetkit",
                "phase2-kickoff",
                "--execute",
                "--emit-pack-dir",
                "docs/artifacts/phase2-kickoff-pack",
                "--evidence-dir",
                "docs/artifacts/phase2-kickoff-pack/evidence",
                "--format",
                "json",
                "--strict",
            ]
        ),
        _run_step(["python", "scripts/check_phase2_kickoff_contract.py"]),
        _run_step(["python", "scripts/check_operator_essentials_contract.py", "--format", "json"]),
    ]
    summary = build_summary(steps)

    summary_json = out_dir / "phase2-start-summary.json"
    summary_md = out_dir / "phase2-start-summary.md"
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_md.write_text(_to_markdown(summary), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("phase2-start-workflow: OK" if summary["ok"] else "phase2-start-workflow: FAIL")
        print(f"- summary_json: {summary_json}")
        print(f"- summary_md: {summary_md}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
