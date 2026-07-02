from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_quality_truth_baseline.py"
CONTRACT = ROOT / "docs" / "contracts" / "quality-truth-baseline.v1.json"


def test_quality_truth_drift_reports_observed_inventory() -> None:
    spec = importlib.util.spec_from_file_location("quality_truth_diagnostics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    payload = module.evaluate_quality_truth(ROOT, CONTRACT)

    assert payload["ok"] is True, json.dumps(payload["observed"], sort_keys=True)
