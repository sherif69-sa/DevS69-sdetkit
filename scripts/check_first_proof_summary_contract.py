from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

_REQUIRED_TOP_LEVEL = (
    "ok",
    "decision",
    "decision_line",
    "strict",
    "selected_python",
    "steps",
    "failed_steps",
)
_REQUIRED_STEP_KEYS = ("name", "command", "returncode", "stdout_log", "stderr_log", "artifact")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("first-proof summary must be a JSON object")
    return payload


def check_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in _REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        errors.append("ok must be a boolean")

    decision = payload.get("decision")
    if decision not in {"SHIP", "NO-SHIP"}:
        errors.append("decision must be either 'SHIP' or 'NO-SHIP'")
    decision_line = payload.get("decision_line")
    if decision_line not in {"FIRST_PROOF_DECISION=SHIP", "FIRST_PROOF_DECISION=NO-SHIP"}:
        errors.append(
            "decision_line must be either 'FIRST_PROOF_DECISION=SHIP' or 'FIRST_PROOF_DECISION=NO-SHIP'"
        )

    strict = payload.get("strict")
    if not isinstance(strict, bool):
        errors.append("strict must be a boolean")

    selected_python = payload.get("selected_python")
    if not isinstance(selected_python, str) or not selected_python:
        errors.append("selected_python must be a non-empty string")

    failed_steps = payload.get("failed_steps")
    if not isinstance(failed_steps, list) or not all(
        isinstance(item, str) for item in failed_steps
    ):
        errors.append("failed_steps must be a list[str]")

    steps = payload.get("steps")
    if not isinstance(steps, list):
        errors.append("steps must be a list")
        return errors

    failing_from_steps: list[str] = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            errors.append(f"steps[{idx}] must be an object")
            continue

        for key in _REQUIRED_STEP_KEYS:
            if key not in step:
                errors.append(f"steps[{idx}] missing key: {key}")

        name = step.get("name")
        command = step.get("command")
        returncode = step.get("returncode")
        stdout_log = step.get("stdout_log")
        stderr_log = step.get("stderr_log")

        if not isinstance(name, str) or not name:
            errors.append(f"steps[{idx}].name must be a non-empty string")
        if not isinstance(command, list) or not all(isinstance(tok, str) for tok in command):
            errors.append(f"steps[{idx}].command must be a list[str]")
        if not isinstance(returncode, int):
            errors.append(f"steps[{idx}].returncode must be an int")
        if not isinstance(stdout_log, str) or not stdout_log:
            errors.append(f"steps[{idx}].stdout_log must be a non-empty string")
        if not isinstance(stderr_log, str) or not stderr_log:
            errors.append(f"steps[{idx}].stderr_log must be a non-empty string")

        if isinstance(name, str) and isinstance(returncode, int) and returncode != 0:
            failing_from_steps.append(name)

    if isinstance(failed_steps, list):
        if sorted(failed_steps) != sorted(failing_from_steps):
            errors.append("failed_steps must match non-zero returncode steps")

    if isinstance(ok, bool):
        expected_ok = len(failing_from_steps) == 0
        if ok != expected_ok:
            errors.append("ok must be true only when all step return codes are zero")
        expected_decision = "SHIP" if expected_ok else "NO-SHIP"
        if decision in {"SHIP", "NO-SHIP"} and decision != expected_decision:
            errors.append("decision must match computed SHIP/NO-SHIP outcome")
        expected_line = f"FIRST_PROOF_DECISION={expected_decision}"
        if (
            decision_line in {"FIRST_PROOF_DECISION=SHIP", "FIRST_PROOF_DECISION=NO-SHIP"}
            and decision_line != expected_line
        ):
            errors.append("decision_line must match computed SHIP/NO-SHIP outcome")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate first-proof summary contract.")
    parser.add_argument(
        "--summary", type=Path, default=Path("build/first-proof/first-proof-summary.json")
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=0.0,
        help="Wait up to this many seconds for the summary file to exist/be readable.",
    )
    parser.add_argument(
        "--wait-interval",
        type=float,
        default=0.5,
        help="Polling interval used with --wait-seconds.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success when the summary file is missing (useful for optional/parallel lanes).",
    )
    args = parser.parse_args(argv)
    deadline = time.monotonic() + max(args.wait_seconds, 0.0)
    last_error: Exception | None = None
    last_contract_errors: list[str] = []
    payload: dict[str, Any] | None = None
    while True:
        try:
            payload = _load(args.summary)
            last_error = None
            contract_errors = check_contract(payload)
            if not contract_errors:
                last_contract_errors = []
                break
            last_contract_errors = contract_errors
            if time.monotonic() >= deadline:
                break
            time.sleep(max(args.wait_interval, 0.05))
            continue
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(max(args.wait_interval, 0.05))

    if payload is None:
        if args.allow_missing and isinstance(last_error, FileNotFoundError):
            result = {
                "ok": True,
                "skipped": True,
                "errors": [],
                "summary": str(args.summary),
                "reason": f"summary missing and --allow-missing enabled: {last_error}",
            }
            if args.format == "json":
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print("first-proof summary contract: skipped (summary missing)")
            return 0
        result = {
            "ok": False,
            "errors": [f"unable to load summary: {last_error}"],
            "summary": str(args.summary),
        }
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("first-proof summary contract: fail")
            print(f"- unable to load summary: {last_error}")
        return 1

    errors = last_contract_errors if last_contract_errors else check_contract(payload)
    result = {"ok": not errors, "errors": errors, "summary": str(args.summary)}

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("first-proof summary contract: ok")
    else:
        print("first-proof summary contract: fail")
        for row in errors:
            print(f"- {row}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
