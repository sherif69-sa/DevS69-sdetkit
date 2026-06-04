#!/usr/bin/env python3
"""Execute full release readiness workflow (startup through wrap handoff)."""

from __future__ import annotations

import argparse
import datetime as _sdetkit_datetime
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

UTC = getattr(_sdetkit_datetime, "UTC", _sdetkit_datetime.timezone.utc)  # noqa: UP017


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        "schema_version": "sdetkit.release_readiness_complete_workflow.v1",
        "generated_at": _utc_now(),
        "ok": not failed,
        "failed_steps": failed,
        "next_actions": [f"Fix failing step: {cmd}" for cmd in failed],
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full release readiness workflow.")
    parser.add_argument("--out-dir", default="build/release-readiness-complete")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    workflow_root = Path("build/release-readiness-workflow")
    hardening_pack = workflow_root / "release-readiness-hardening-completion-report-pack"
    wrap_pack = workflow_root / "release-readiness-wrap-handoff-completion-report-pack"
    steps = [
        _run_step(["python", "scripts/release_readiness_start_workflow.py", "--format", "json"]),
        _run_step(
            [
                "python",
                "scripts/check_release_readiness_start_summary_contract.py",
                "--format",
                "json",
            ]
        ),
        _run_step(
            [
                "python",
                "scripts/release_readiness_status_report.py",
                "--format",
                "json",
                "--out",
                "build/release-readiness-start/release-readiness-status.json",
            ]
        ),
        _run_step(
            [
                "python",
                "-m",
                "sdetkit",
                "release-readiness-hardening-completion-report",
                "--emit-pack-dir",
                str(hardening_pack),
                "--execute",
                "--evidence-dir",
                str(hardening_pack / "evidence"),
                "--format",
                "json",
            ]
        ),
        _run_step(
            [
                "python",
                "-m",
                "sdetkit",
                "release-readiness-wrap-handoff-completion-report",
                "--emit-pack-dir",
                str(wrap_pack),
                "--execute",
                "--evidence-dir",
                str(wrap_pack / "evidence"),
                "--format",
                "json",
            ]
        ),
    ]
    summary = build_summary(steps)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "release-readiness-complete-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "release-readiness-complete-workflow: OK"
            if summary["ok"]
            else "release-readiness-complete-workflow: FAIL"
        )
        print(f"- summary: {summary_path}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
