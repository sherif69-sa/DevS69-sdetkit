from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_DIMENSIONS = ("onboarding", "release", "ops", "quality")


def _validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "2":
        errors.append("schema_version must be '2'")
    for key in ("score", "band", "dimensions", "graded_dimensions", "weights", "signals"):
        if key not in payload:
            errors.append(f"missing key: {key}")
    if not isinstance(payload.get("dimensions"), dict):
        errors.append("dimensions must be an object")
    if not isinstance(payload.get("graded_dimensions"), dict):
        errors.append("graded_dimensions must be an object")
    if not isinstance(payload.get("weights"), dict):
        errors.append("weights must be an object")
    if not isinstance(payload.get("signals"), dict):
        errors.append("signals must be an object")

    for dim in REQUIRED_DIMENSIONS:
        if dim not in payload.get("dimensions", {}):
            errors.append(f"dimensions missing '{dim}'")
        if dim not in payload.get("graded_dimensions", {}):
            errors.append(f"graded_dimensions missing '{dim}'")
        if dim not in payload.get("weights", {}):
            errors.append(f"weights missing '{dim}'")
        if dim not in payload.get("signals", {}):
            errors.append(f"signals missing '{dim}'")

    weight_total = sum(
        float(payload.get("weights", {}).get(dim, 0.0)) for dim in REQUIRED_DIMENSIONS
    )
    if abs(weight_total - 1.0) > 0.001:
        errors.append("weights must sum to 1.0 (+/- 0.001)")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_adoption_scorecard_v2_contract.py")
    parser.add_argument("--infile", default=".sdetkit/out/adoption-scorecard.json")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    ns = parser.parse_args(argv)

    path = Path(ns.infile)
    if not path.exists():
        payload: dict[str, Any] = {"ok": False, "errors": [f"missing file: {path}"]}
        if ns.format == "json":
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"adoption-scorecard-contract: FAIL ({payload['errors'][0]})")
        return 2

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("scorecard payload must be a JSON object")
    errors = _validate(raw)
    ok = len(errors) == 0
    result = {"ok": ok, "errors": errors, "path": str(path)}
    if ns.format == "json":
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"adoption-scorecard-contract: {'OK' if ok else 'FAIL'}")
        for error in errors:
            print(f"- {error}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
