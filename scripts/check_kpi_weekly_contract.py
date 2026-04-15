#!/usr/bin/env python3
"""Validate a KPI weekly payload against repo KPI schema contract (lightweight checker)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_metric(metric: dict[str, Any], metric_key: str, required_fields: list[str]) -> None:
    for key in required_fields:
        _expect(key in metric, f"{metric_key}: missing field '{key}'")

    _expect(isinstance(metric["unit"], str), f"{metric_key}.unit must be string")
    _expect(isinstance(metric["quality"], str), f"{metric_key}.quality must be string")
    _expect(isinstance(metric["source"], str), f"{metric_key}.source must be string")
    _expect(metric["quality"] in {"seed", "provisional", "stable"}, f"{metric_key}.quality invalid")


def _validate(schema: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    required_top = list(schema.get("required", []))
    for key in required_top:
        _expect(key in payload, f"missing top-level required field '{key}'")

    _expect(payload.get("schema_version") == schema.get("properties", {}).get("schema_version", {}).get("const"), "schema_version mismatch")

    kpis = payload.get("kpis")
    _expect(isinstance(kpis, dict), "kpis must be object")

    required_kpis = list(schema.get("properties", {}).get("kpis", {}).get("required", []))
    metric_required = list(schema.get("$defs", {}).get("metric", {}).get("required", []))
    for metric_key in required_kpis:
        _expect(metric_key in kpis, f"missing required KPI '{metric_key}'")
        _expect(isinstance(kpis[metric_key], dict), f"{metric_key} must be object")
        _validate_metric(kpis[metric_key], metric_key, metric_required)

    return {
        "ok": True,
        "schema_version": payload.get("schema_version"),
        "week_ending": payload.get("week_ending"),
        "required_kpi_count": len(required_kpis),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check KPI weekly payload contract")
    ap.add_argument("--schema", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    args = ap.parse_args()

    schema = json.loads(Path(args.schema).read_text())
    payload = json.loads(Path(args.payload).read_text())
    report = _validate(schema, payload)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
