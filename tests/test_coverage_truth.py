from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/check_coverage_truth.py"
CONTRACT_PATH = ROOT / "docs/contracts/quality-truth-baseline.v1.json"


def _module():
    spec = importlib.util.spec_from_file_location("check_coverage_truth", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _coverage(path: Path, *, critical_missing: int = 0, whole_percent: float = 70.0) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    files = {}
    for critical_path in contract["coverage"]["critical_spine"]["files"]:
        statements = 20
        files[critical_path] = {
            "summary": {
                "covered_lines": statements - critical_missing,
                "num_statements": statements,
            }
        }
    path.write_text(
        json.dumps(
            {
                "files": files,
                "totals": {
                    "covered_lines": 700,
                    "num_statements": 1000,
                    "percent_covered": whole_percent,
                },
            }
        ),
        encoding="utf-8",
    )


def test_coverage_truth_preserves_critical_threshold_and_records_whole_package(
    tmp_path: Path,
) -> None:
    coverage_path = tmp_path / "coverage.json"
    _coverage(coverage_path)

    payload = _module().evaluate_coverage_truth(coverage_path, CONTRACT_PATH)

    assert payload["ok"] is True
    assert payload["critical_spine"]["percent"] == 100.0
    assert payload["critical_spine"]["minimum_percent"] == 95.0
    assert payload["whole_package"]["percent"] == 70.0
    assert payload["whole_package"]["baseline_enforced"] is False


def test_coverage_truth_rejects_critical_spine_regression(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"
    _coverage(coverage_path, critical_missing=2)

    payload = _module().evaluate_coverage_truth(coverage_path, CONTRACT_PATH)

    assert payload["ok"] is False
    assert payload["critical_spine"]["percent"] == 90.0
    assert payload["checks"]["critical_spine_meets_minimum"] is False


def test_coverage_truth_rejects_missing_critical_file(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"
    _coverage(coverage_path)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    removed = next(iter(coverage["files"]))
    coverage["files"].pop(removed)
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")

    payload = _module().evaluate_coverage_truth(coverage_path, CONTRACT_PATH)

    assert payload["ok"] is False
    assert payload["critical_spine"]["missing_files"] == [removed]
    assert payload["checks"]["critical_files_present"] is False
