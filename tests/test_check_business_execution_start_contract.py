from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_start_contract.py"
)
_SPEC = importlib.util.spec_from_file_location("check_business_execution_start_contract_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(contract)


def test_validate_contract_passes_for_valid_payload() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-start.v1",
        "owners": {
            "program_owner": "A",
            "gtm_owner": "B",
            "commercial_owner": "C",
            "solutions_owner": "D",
            "ops_owner": "E",
        },
        "status": "go",
        "next_action": "Run execution week with live owners and baseline KPIs.",
    }
    assert contract.validate_contract(payload) == []


def test_validate_contract_rejects_go_with_tbd_owners() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-start.v1",
        "owners": {
            "program_owner": "TBD",
            "gtm_owner": "B",
            "commercial_owner": "C",
            "solutions_owner": "D",
            "ops_owner": "E",
        },
        "status": "go",
        "next_action": "Run execution week with live owners and baseline KPIs.",
    }
    errors = contract.validate_contract(payload)
    assert "status=go is invalid when owners are TBD" in errors


def test_main_require_go_fails_for_non_go_status(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-start.v1",
                "owners": {
                    "program_owner": "TBD",
                    "gtm_owner": "TBD",
                    "commercial_owner": "TBD",
                    "solutions_owner": "TBD",
                    "ops_owner": "TBD",
                },
                "status": "needs-owner-assignment",
                "next_action": "Assign all owners, then rerun this command.",
            }
        ),
        encoding="utf-8",
    )
    rc = contract.main(["--artifact", str(artifact), "--require-go"])
    assert rc == 1
