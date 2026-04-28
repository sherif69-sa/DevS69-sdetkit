from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_next_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_next_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
next_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(next_contract)


def test_validate_next_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-next.v1",
        "pending_count": 1,
        "next_tasks": ["A"],
        "recommended_command": 'python scripts/business_execution_progress.py --done "A"',
    }
    assert next_contract.validate_next_contract(payload) == []


def test_main_fails_for_invalid_pending_count(tmp_path: Path) -> None:
    artifact = tmp_path / "next.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-next.v1",
                "pending_count": "1",
                "next_tasks": ["A"],
                "recommended_command": None,
            }
        ),
        encoding="utf-8",
    )
    rc = next_contract.main(["--artifact", str(artifact)])
    assert rc == 1
