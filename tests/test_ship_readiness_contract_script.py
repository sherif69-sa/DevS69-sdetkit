from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    module_path = Path("scripts/check_ship_readiness_contract.py")
    spec = spec_from_file_location("check_ship_readiness_contract", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_checker_passes_for_valid_payload() -> None:
    checker = _load_module()
    payload = {
        "contract": {"schema_version": "sdetkit.ship_readiness.v1"},
        "summary": {
            "gate_fast_ok": True,
            "gate_release_ok": True,
            "doctor_ok": True,
            "release_readiness_ok": True,
            "all_green": True,
            "decision": "go",
            "blockers": [],
            "blocker_catalog": [],
        },
        "runs": [
            {
                "id": "doctor",
                "command": "python -m sdetkit doctor --format json",
                "return_code": 0,
                "ok": True,
                "error_kind": "none",
                "attempts": 1,
            }
        ],
    }

    assert checker.check_contract(payload) == []


def test_contract_checker_cli_reports_missing_keys(tmp_path: Path, capsys) -> None:
    checker = _load_module()
    summary = tmp_path / "summary.json"
    summary.write_text("{}", encoding="utf-8")

    rc = checker.main(["--summary", str(summary), "--format", "json"])

    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert any("missing top-level key" in row for row in out["errors"])
