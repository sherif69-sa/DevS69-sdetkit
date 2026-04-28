from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_business_execution_inputs_contract.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "check_business_execution_inputs_contract_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
inputs_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inputs_contract)


def test_validate_inputs_contract_passes() -> None:
    payload = {
        "schema_version": "sdetkit.business-execution-inputs.v1",
        "challenge_prompt": {
            "path": "a.md",
            "size_bytes": 1,
            "sha256": "x",
            "line_count": 1,
            "first_heading": "h",
        },
        "guidelines_zip": {
            "path": "a.zip",
            "size_bytes": 2,
            "sha256": "y",
            "entry_count": 2,
            "entries_preview": ["a"],
        },
    }
    assert inputs_contract.validate_inputs_contract(payload) == []


def test_main_fails_when_zip_exceeds_limit(tmp_path: Path) -> None:
    artifact = tmp_path / "inputs.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.business-execution-inputs.v1",
                "challenge_prompt": None,
                "guidelines_zip": {
                    "path": "a.zip",
                    "size_bytes": 2,
                    "sha256": "y",
                    "entry_count": 30,
                    "entries_preview": ["a"],
                },
            }
        ),
        encoding="utf-8",
    )
    rc = inputs_contract.main(["--artifact", str(artifact)])
    assert rc == 1
