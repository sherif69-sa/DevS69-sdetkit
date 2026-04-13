from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_ARTIFACT_KEYS = (
    "golden_path_health",
    "canonical_path_drift",
    "legacy_command_analyzer",
    "adoption_scorecard",
    "operator_onboarding_summary",
)


def _validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append("status must be 'ok'")
    if payload.get("observability_contract_version") != "2":
        errors.append("observability_contract_version must be '2'")
    if not isinstance(payload.get("captured_at"), str):
        errors.append("captured_at must be a string")

    summary = payload.get("freshness_summary")
    if not isinstance(summary, dict):
        errors.append("freshness_summary must be an object")
    else:
        for key in ("present", "missing", "invalid_json", "stale", "fresh"):
            if not isinstance(summary.get(key), int):
                errors.append(f"freshness_summary.{key} must be int")

    observability = payload.get("observability")
    if not isinstance(observability, dict):
        errors.append("observability must be an object")
        return errors

    for key in EXPECTED_ARTIFACT_KEYS:
        item = observability.get(key)
        if not isinstance(item, dict):
            errors.append(f"observability.{key} must be an object")
            continue
        for field in ("state", "path", "stale", "stale_threshold_seconds"):
            if field not in item:
                errors.append(f"observability.{key} missing {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_observability_v2_contract.py")
    parser.add_argument("--infile")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    ns = parser.parse_args(argv)

    if ns.infile:
        payload = json.loads(Path(ns.infile).read_text(encoding="utf-8"))
    else:
        from sdetkit import serve

        payload = serve._observability_snapshot(Path("."))
    if not isinstance(payload, dict):
        raise TypeError("observability payload must be a JSON object")

    errors = _validate(payload)
    ok = len(errors) == 0
    result = {"ok": ok, "errors": errors}

    if ns.format == "json":
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"observability-contract: {'OK' if ok else 'FAIL'}")
        for error in errors:
            print(f"- {error}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
