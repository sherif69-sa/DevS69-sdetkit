#!/usr/bin/env python3
"""Validate phase1 baseline summary contract payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_TOP_LEVEL = {
    "schema_version": "sdetkit.phase1_baseline.v1",
    "generated_at_utc": str,
    "out_dir": str,
    "checks": list,
    "ok": bool,
}
REQUIRED_CHECK_KEYS = {"id": str, "ok": bool, "rc": int, "stdout_log": str, "stderr_log": str}


def _check_type(value: object, expected: object) -> bool:
    if isinstance(expected, str):
        return value == expected
    if isinstance(expected, type):
        return isinstance(value, expected)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument(
        "--require-logs",
        action="store_true",
        help="Fail if stdout/stderr log paths referenced in checks do not exist.",
    )
    ns = ap.parse_args()

    summary_path = Path(ns.summary)
    failures: list[str] = []
    checks: list[dict[str, object]] = []

    exists = summary_path.is_file()
    checks.append({"id": "summary_exists", "ok": exists, "path": str(summary_path)})
    if not exists:
        failures.append(f"missing summary file: {summary_path}")
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_baseline_summary_contract.v1",
            "summary": str(summary_path),
            "checks": checks,
            "failures": failures,
        }
        if ns.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("phase1-baseline-summary-contract: FAIL")
            for item in failures:
                print(f"- {item}")
        return 1

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        failures.append("summary payload is not a JSON object")
        data = {}

    for key, expected in REQUIRED_TOP_LEVEL.items():
        present = key in data
        checks.append({"id": f"top_level::{key}::present", "ok": present})
        if not present:
            failures.append(f"missing top-level key: {key}")
            continue

        valid_type = _check_type(data.get(key), expected)
        checks.append({"id": f"top_level::{key}::type_or_value", "ok": valid_type})
        if not valid_type:
            failures.append(f"invalid value/type for key: {key}")

    check_rows = data.get("checks")
    if isinstance(check_rows, list):
        for idx, row in enumerate(check_rows):
            row_id = f"check_row::{idx}"
            is_obj = isinstance(row, dict)
            checks.append({"id": f"{row_id}::object", "ok": is_obj})
            if not is_obj:
                failures.append(f"check row {idx} is not an object")
                continue

            for key, expected_type in REQUIRED_CHECK_KEYS.items():
                has_key = key in row
                checks.append({"id": f"{row_id}::{key}::present", "ok": has_key})
                if not has_key:
                    failures.append(f"check row {idx} missing key: {key}")
                    continue

                type_ok = isinstance(row[key], expected_type)
                checks.append({"id": f"{row_id}::{key}::type", "ok": type_ok})
                if not type_ok:
                    failures.append(f"check row {idx} key '{key}' has wrong type")

            if ns.require_logs:
                for log_key in ("stdout_log", "stderr_log"):
                    log_path = Path(str(row.get(log_key, "")))
                    log_exists = log_path.is_file()
                    checks.append({"id": f"{row_id}::{log_key}::exists", "ok": log_exists})
                    if not log_exists:
                        failures.append(f"check row {idx} referenced missing log: {log_path}")

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.phase1_baseline_summary_contract.v1",
        "summary": str(summary_path),
        "checks": checks,
        "failures": failures,
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "phase1-baseline-summary-contract: OK"
            if payload["ok"]
            else "phase1-baseline-summary-contract: FAIL"
        )
        for row in checks:
            print(f"[{'OK' if row['ok'] else 'FAIL'}] {row['id']}")
        if failures:
            for item in failures:
                print(f"- {item}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
