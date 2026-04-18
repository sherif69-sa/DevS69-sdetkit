#!/usr/bin/env python3
"""Run the full Phase 1 operational sequence and persist execution evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_command_plan(include_closeout: bool = False) -> list[list[str]]:
    commands = [
        ["make", "phase1-baseline"],
        ["make", "phase1-status"],
        ["make", "phase1-next"],
        ["make", "phase1-ops-snapshot"],
        ["make", "phase1-dashboard"],
        ["make", "phase1-weekly-pack"],
        ["make", "phase1-control-loop"],
    ]
    if include_closeout:
        commands.append(["make", "phase1-closeout"])
    return commands


def run_plan(commands: list[list[str]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    overall_ok = True

    for cmd in commands:
        started = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration_ms = int((time.time() - started) * 1000)
        ok = proc.returncode == 0
        rows.append(
            {
                "command": " ".join(cmd),
                "ok": ok,
                "returncode": proc.returncode,
                "duration_ms": duration_ms,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        )
        if not ok:
            overall_ok = False
            break

    return {
        "ok": overall_ok,
        "steps": rows,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 1 run-all execution report",
        "",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Overall ok: {payload.get('ok', False)}",
        "",
        "## Steps",
    ]
    for step in payload.get("steps", []):
        lines.append(
            f"- `{step.get('command')}` -> ok={step.get('ok')} rc={step.get('returncode')} duration_ms={step.get('duration_ms')}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full Phase 1 sequence.")
    parser.add_argument("--include-closeout", action="store_true")
    parser.add_argument("--out-json", default="build/phase1-baseline/phase1-run-all.json")
    parser.add_argument("--out-md", default="build/phase1-baseline/phase1-run-all.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    commands = build_command_plan(include_closeout=args.include_closeout)
    executed = run_plan(commands)

    payload = {
        "schema_version": "sdetkit.phase1_run_all.v1",
        "generated_at": _utc_now(),
        "ok": executed["ok"],
        "steps": executed["steps"],
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_to_markdown(payload), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-run-all: OK" if payload["ok"] else "phase1-run-all: FAIL")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
