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


def test_contract_helpers_cover_missing_package_and_missing_surface(tmp_path, monkeypatch):
    from importlib import metadata

    from sdetkit import contract

    def _raise_not_found(_name: str):
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(contract.metadata, "version", _raise_not_found)
    assert contract._tool_version() == "0+unknown"
    assert contract._public_surface_contract(tmp_path) == {}


def test_contract_main_non_runtime_action_returns_2(monkeypatch):
    from types import SimpleNamespace

    from sdetkit import contract

    monkeypatch.setattr(
        contract.argparse.ArgumentParser,
        "parse_args",
        lambda self, argv=None: SimpleNamespace(action="other", format="text", repo_root="."),
    )
    assert contract.main([]) == 2


def test_contract_module_invocation_executes_main_guard() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sdetkit.contract", "runtime", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "runtime_contract_version" in result.stdout
