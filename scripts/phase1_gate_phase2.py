#!/usr/bin/env python3
"""Gate Phase 2 entry based on Phase 1 completion artifacts."""

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


def build_gate_result(finish_signal: dict[str, Any], artifact_set: dict[str, Any]) -> dict[str, Any]:
    complete = finish_signal.get("status") == "complete"
    artifacts_ok = bool(artifact_set.get("ok", False))
    ready = bool(complete and artifacts_ok)

    return {
        "schema_version": "sdetkit.phase1_gate_phase2.v1",
        "ready_for_phase2": ready,
        "finish_status": finish_signal.get("status", "unknown"),
        "finish_gate_ok": bool(finish_signal.get("gate_ok", False)),
        "artifacts_ok": artifacts_ok,
        "blocking_required_checks": finish_signal.get("blocking_required_checks", []),
        "missing_artifacts": artifact_set.get("missing", []),
        "next_step": "make phase1-retire-plan" if ready else "make phase1-next-pass && make phase1-blocker-register",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate gate to Phase 2.")
    parser.add_argument("--finish-signal", default="build/phase1-baseline/phase1-finish-signal.json")
    parser.add_argument("--artifact-set", default="build/phase1-baseline/phase1-artifact-set.json")
    parser.add_argument("--auto-retire", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    finish = _load_json(Path(args.finish_signal))
    artifacts = _load_json(Path(args.artifact_set))

    if not finish or not artifacts:
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_gate_phase2.v1",
            "reason": "missing finish-signal or artifact-set payload",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-gate-phase2: FAIL ({payload['reason']})")
        return 1

    gate = build_gate_result(finish, artifacts)
    gate["ok"] = True

    if args.auto_retire and gate["ready_for_phase2"]:
        proc = subprocess.run(["make", "phase1-retire-plan"], capture_output=True, text=True)
        gate["auto_retire"] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    if args.format == "json":
        print(json.dumps(gate, indent=2, sort_keys=True))
    else:
        print("phase1-gate-phase2: READY" if gate["ready_for_phase2"] else "phase1-gate-phase2: BLOCKED")
        print(f"- finish_status: {gate['finish_status']}")
        print(f"- artifacts_ok: {gate['artifacts_ok']}")
        print(f"- next_step: {gate['next_step']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
