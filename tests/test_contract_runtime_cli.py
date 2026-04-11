from __future__ import annotations

import json
import subprocess
import sys


def test_contract_runtime_json_is_adopter_focused_and_versioned() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sdetkit", "contract", "runtime", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)

    assert payload["runtime_contract_version"] == "sdetkit.runtime.contract.v1"
    assert payload["tool"]["name"] == "sdetkit"
    assert payload["recommended_install"]["pip_git"].startswith("python -m pip install")
    assert payload["stable_machine_outputs"]["review_operator_json"]["contract_version"] == (
        "sdetkit.review.contract.v1"
    )
    assert payload["container_runtime"]["dockerfile"] == "Dockerfile.runtime"
    assert payload["container_runtime"]["default_entrypoint"] == "sdetkit"


def test_contract_runtime_text_includes_core_adoption_fields() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sdetkit", "contract", "runtime"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    out = result.stdout
    assert "runtime_contract_version: sdetkit.runtime.contract.v1" in out
    assert "stable_machine_output:" in out
    assert "contract_version: sdetkit.review.contract.v1" in out
