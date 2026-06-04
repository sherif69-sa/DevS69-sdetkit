#!/usr/bin/env python3
"""Gate release readiness entry based on baseline completion artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_gate_result(
    readiness_signal: dict[str, Any], artifact_set: dict[str, Any]
) -> dict[str, Any]:
    complete = readiness_signal.get("status") == "complete"
    artifacts_ok = bool(artifact_set.get("ok", False))
    ready = bool(complete and artifacts_ok)

    return {
        "schema_version": "sdetkit.baseline_release_readiness_gate.v1",
        "ready_for_release readiness": ready,
        "finish_status": readiness_signal.get("status", "unknown"),
        "finish_gate_ok": bool(readiness_signal.get("gate_ok", False)),
        "artifacts_ok": artifacts_ok,
        "blocking_required_checks": readiness_signal.get("blocking_required_checks", []),
        "missing_artifacts": artifact_set.get("missing", []),
        "next_step": "make baseline-transition-plan"
        if ready
        else "make baseline-followup-pass && make baseline-blocker-register",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate gate to release readiness.")
    parser.add_argument(
        "--readiness-signal", default="build/baseline/baseline-readiness-signal.json"
    )
    parser.add_argument("--artifact-set", default="build/baseline/baseline-artifact-set.json")
    parser.add_argument("--auto-retire", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    finish = _load_json(Path(args.readiness_signal))
    artifacts = _load_json(Path(args.artifact_set))

    if not finish or not artifacts:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.baseline_release_readiness_gate.v1",
            "reason": "missing readiness signal or artifact-set payload",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"baseline-release-readiness-gate: FAIL ({payload['reason']})")
        return 1

    gate = build_gate_result(finish, artifacts)
    gate["ok"] = True

    if args.auto_retire and gate["ready_for_release readiness"]:
        proc = subprocess.run(["make", "baseline-transition-plan"], capture_output=True, text=True)
        gate["auto_retire"] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    if args.format == "json":
        print(json.dumps(gate, indent=2, sort_keys=True))
    else:
        print(
            "baseline-release-readiness-gate: READY"
            if gate["ready_for_release readiness"]
            else "baseline-release-readiness-gate: BLOCKED"
        )
        print(f"- finish_status: {gate['finish_status']}")
        print(f"- artifacts_ok: {gate['artifacts_ok']}")
        print(f"- next_step: {gate['next_step']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
