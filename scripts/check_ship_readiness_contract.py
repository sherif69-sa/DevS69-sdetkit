from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_REQUIRED_TOP_LEVEL = ("contract", "summary", "runs")
_REQUIRED_SUMMARY = (
    "gate_fast_ok",
    "gate_release_ok",
    "doctor_ok",
    "release_readiness_ok",
    "all_green",
    "decision",
    "blockers",
    "blocker_catalog",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ship summary must be a JSON object")
    return payload


def check_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in _REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in _REQUIRED_SUMMARY:
            if key not in summary:
                errors.append(f"summary missing key: {key}")
    else:
        errors.append("summary must be an object")

    runs = payload.get("runs")
    if not isinstance(runs, list):
        errors.append("runs must be a list")
    else:
        for idx, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                errors.append(f"runs[{idx}] must be an object")
                continue
            for key in ("id", "command", "return_code", "ok", "error_kind", "attempts"):
                if key not in run:
                    errors.append(f"runs[{idx}] missing key: {key}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ship-readiness summary contract.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payload = _load(args.summary)
    errors = check_contract(payload)
    result = {"ok": not errors, "errors": errors, "summary": str(args.summary)}

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print("ship-readiness contract: ok")
        else:
            print("ship-readiness contract: fail")
            for row in errors:
                print(f"- {row}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
