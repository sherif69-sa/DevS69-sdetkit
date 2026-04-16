from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sdetkit import enterprise_assessment as ea


def _load_contract_module():
    module_path = Path("scripts/check_enterprise_assessment_contract.py")
    spec = spec_from_file_location("check_enterprise_assessment_contract", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_script_passes_for_enterprise_assessment_payload(tmp_path: Path) -> None:
    contract = _load_contract_module()
    payload = ea.build_enterprise_assessment(tmp_path)
    payload["trend"] = {"has_baseline": False, "score_delta": None, "status": "no-baseline"}
    payload["contract"] = {
        "schema_version": "sdetkit.enterprise_assessment.v2",
        "generated_at_utc": "2026-04-16T00:00:00Z",
        "contract_id": "ea-demo",
    }

    errors = contract.check_contract(payload)

    assert errors == []


def test_contract_script_cli_fails_when_required_keys_missing(tmp_path: Path, capsys) -> None:
    contract = _load_contract_module()
    summary = tmp_path / "summary.json"
    summary.write_text("{}", encoding="utf-8")

    rc = contract.main(["--summary", str(summary), "--format", "json"])

    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert any("missing top-level key" in row for row in out["errors"])
