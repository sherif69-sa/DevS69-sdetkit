from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _percentage(covered: int, statements: int) -> float:
    return round((100.0 * covered / statements) if statements else 100.0, 2)


def evaluate_coverage_truth(
    coverage_path: Path,
    contract_path: Path,
) -> dict[str, object]:
    coverage = _load_object(coverage_path)
    contract = _load_object(contract_path)
    coverage_contract = contract["coverage"]
    critical_contract = coverage_contract["critical_spine"]
    whole_contract = coverage_contract["whole_package"]

    files = coverage.get("files")
    totals = coverage.get("totals")
    if not isinstance(files, dict) or not isinstance(totals, dict):
        raise ValueError("coverage JSON is missing files or totals")

    required_files = [str(item) for item in critical_contract["files"]]
    missing_files = [path for path in required_files if path not in files]
    critical_covered = 0
    critical_statements = 0
    for path in required_files:
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue
        summary = entry.get("summary")
        if not isinstance(summary, dict):
            continue
        critical_covered += int(summary.get("covered_lines", 0))
        critical_statements += int(summary.get("num_statements", 0))

    critical_percent = _percentage(critical_covered, critical_statements)
    whole_percent = round(float(totals.get("percent_covered", 0.0)), 2)
    critical_minimum = float(critical_contract["minimum_percent"])
    baseline = whole_contract.get("current_percent")
    baseline_reviewed = bool(whole_contract.get("blocking_threshold_reviewed"))
    whole_non_regression = (
        not baseline_reviewed or baseline is None or whole_percent >= float(baseline)
    )

    checks = {
        "critical_files_present": not missing_files,
        "critical_spine_meets_minimum": critical_percent >= critical_minimum,
        "whole_package_non_regression": whole_non_regression,
        "whole_package_measurement_present": float(totals.get("num_statements", 0)) > 0,
    }
    return {
        "schema_version": "sdetkit.coverage_truth_check.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "critical_spine": {
            "covered_lines": critical_covered,
            "num_statements": critical_statements,
            "percent": critical_percent,
            "minimum_percent": critical_minimum,
            "missing_files": missing_files,
        },
        "whole_package": {
            "covered_lines": int(totals.get("covered_lines", 0)),
            "num_statements": int(totals.get("num_statements", 0)),
            "percent": whole_percent,
            "reviewed_baseline_percent": baseline,
            "baseline_enforced": baseline_reviewed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate coverage truth evidence")
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = evaluate_coverage_truth(args.coverage, args.contract)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
