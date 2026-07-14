from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

pytest.register_assert_rewrite("adoption_surface_contracts")
import adoption_surface_contracts as _legacy  # noqa: E402

_REPLACED_CONTRACTS = {
    "test_adoption_surface_recommended_proof_commands_include_operator_purpose",
    "test_adoption_surface_detects_multi_language_evidence_without_running_commands",
}

for _name, _value in vars(_legacy).items():
    if _name.startswith("test_") and _name not in _REPLACED_CONTRACTS:
        globals()[_name] = _value


def _write(path: Path, text: str = "") -> None:
    _legacy._write(path, text)


def _commands(payload: dict) -> set[str]:
    return _legacy._commands(payload)


def _proof_command(payload: dict, command: str) -> dict:
    return _legacy._proof_command(payload, command)


def _names(items: list[dict]) -> set[str]:
    return _legacy._names(items)


def test_adoption_surface_recommended_proof_commands_include_operator_purpose(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(
        tmp_path / "Makefile",
        ".PHONY: proof-after-format\nproof-after-format:\n\tpython -m pre_commit run -a\n",
    )
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest"}}),
    )
    _write(tmp_path / "package-lock.json", "{}\n")
    _write(tmp_path / "go.mod", "module example\n")
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'example'\n")
    _write(tmp_path / "pom.xml", "<project />\n")
    _write(tmp_path / "service" / "App.csproj", "<Project />\n")

    payload = _legacy.discover_adoption_surface(tmp_path)
    commands = payload["recommended_proof_commands"]

    assert commands
    assert all(
        {"surface", "command", "confidence", "purpose"} <= set(command)
        for command in commands
    )
    assert (
        _proof_command(payload, "python -m pytest -q -o addopts=")["purpose"] == "test"
    )
    assert _proof_command(payload, "make proof-after-format")["purpose"] == "quality"
    assert (
        _proof_command(
            payload, "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict"
        )["purpose"]
        == "docs"
    )
    assert _proof_command(payload, "npm test")["purpose"] == "test"
    assert _proof_command(payload, "go test ./...")["purpose"] == "test"
    assert _proof_command(payload, "cargo test")["purpose"] == "test"
    assert _proof_command(payload, "mvn test")["purpose"] == "test"
    assert "dotnet test" not in _commands(payload)
    assert (
        ".NET project service/App.csproj detected but test-project evidence is not proven"
        in payload["review_first_unknowns"]
    )


def test_adoption_surface_detects_multi_language_evidence_without_running_commands(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "go.mod", "module example\n")
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'example'\n")
    _write(tmp_path / "pom.xml", "<project />\n")
    _write(tmp_path / "service" / "App.csproj", "<Project />\n")
    _write(tmp_path / "coverage.xml", "<coverage />\n")

    payload = _legacy.discover_adoption_surface(tmp_path)

    assert {"go", "rust", "java", "dotnet"} <= _names(payload["detected_languages"])
    assert {"go_modules", "cargo", "maven", "nuget"} <= _names(
        payload["package_managers"]
    )
    assert "go test ./..." in _commands(payload)
    assert "cargo test" in _commands(payload)
    assert "mvn test" in _commands(payload)
    assert "dotnet test" not in _commands(payload)
    assert (
        ".NET project service/App.csproj detected but test-project evidence is not proven"
        in payload["review_first_unknowns"]
    )
    assert payload["artifact_surfaces"] == [
        {"name": "coverage", "paths": ["coverage.xml"]}
    ]
