#!/usr/bin/env python3
"""Run the full baseline operational sequence and persist execution evidence."""

from __future__ import annotations

import argparse
import datetime as _sdetkit_datetime
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

UTC = getattr(_sdetkit_datetime, "UTC", _sdetkit_datetime.timezone.utc)  # noqa: UP017


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_command_plan(
    include_completion_report: bool = False, *, include: bool | None = None
) -> list[list[str]]:
    if include is not None:
        include_completion_report = include
    commands = [
        ["make", "baseline-baseline"],
        ["make", "baseline-status"],
        ["make", "baseline-next"],
        ["make", "baseline-ops-snapshot"],
        ["make", "baseline-dashboard"],
        ["make", "baseline-weekly-pack"],
        ["make", "baseline-control-loop"],
    ]
    if include_completion_report:
        commands.append(["make", "baseline-completion-report"])
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
        "# baseline run-all execution report",
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
    parser = argparse.ArgumentParser(description="Run full baseline sequence.")
    parser.add_argument("--include-completion-report", action="store_true")
    parser.add_argument("--out-json", default="build/baseline/baseline-run-all.json")
    parser.add_argument("--out-md", default="build/baseline/baseline-run-all.md")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    commands = build_command_plan(include=args.include_completion_report)
    executed = run_plan(commands)

    payload = {
        "schema_version": "sdetkit.baseline_run_all.v1",
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
        print("baseline-run-all: OK" if payload["ok"] else "baseline-run-all: FAIL")
        print(f"- json: {out_json}")
        print(f"- markdown: {out_md}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
