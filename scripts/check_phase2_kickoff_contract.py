#!/usr/bin/env python3
"""Validate phase2-kickoff contract by executing the lane and checking evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def _evidence_path(root: Path) -> Path:
    return root / "build/phase2-workflow/phase2-kickoff-pack/evidence/phase2-kickoff-execution-summary.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate phase2-kickoff contract.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    command = [
        "python",
        "-m",
        "sdetkit",
        "phase2-kickoff",
        "--root",
        str(root),
        "--emit-pack-dir",
        str(root / "build/phase2-workflow/phase2-kickoff-pack"),
        "--evidence-dir",
        str(root / "build/phase2-workflow/phase2-kickoff-pack/evidence"),
        "--format",
        "json",
        "--strict",
    ]
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = "src" if not existing else f"src:{existing}"
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    errors: list[str] = []

    payload: dict[str, object] = {}
    if proc.returncode != 0:
        errors.append("phase2-kickoff strict run failed")

    stdout = proc.stdout.strip()
    if not stdout:
        errors.append("phase2-kickoff emitted no JSON output")
    else:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"phase2-kickoff output is not valid JSON: {exc}")

    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    if isinstance(summary, dict):
        if not bool(summary.get("strict_pass", False)):
            errors.append("phase2-kickoff summary.strict_pass=false")
        if int(summary.get("activation_score", 0)) < 95:
            errors.append("phase2-kickoff activation_score below 95")

    if not args.skip_evidence:
        evidence = _evidence_path(root)
        if not evidence.exists():
            errors.append(f"missing evidence file: {evidence}")
        else:
            data = json.loads(evidence.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                errors.append("execution evidence payload must be a JSON object")

    result = {
        "ok": not errors,
        "schema_version": "sdetkit.phase2_kickoff_contract.v2",
        "score": int(summary.get("activation_score", 0)) if isinstance(summary, dict) else 0,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
