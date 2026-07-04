from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


@pytest.mark.parametrize(
    ("lockfile", "expected_manager", "expected_command"),
    [
        ("package-lock.json", "npm", "npm test"),
        ("pnpm-lock.yaml", "pnpm", "pnpm test"),
        ("yarn.lock", "yarn", "yarn test"),
    ],
)
def test_adoption_surface_recommends_javascript_test_command_for_detected_package_manager(
    tmp_path: Path,
    lockfile: str,
    expected_manager: str,
    expected_command: str,
) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest"}}),
    )
    _write(tmp_path / lockfile, "# lockfile evidence\n")

    payload = discover_adoption_surface(tmp_path)
    managers = {str(item["name"]) for item in payload["package_managers"]}
    runners = {str(item["name"]): item for item in payload["test_runners"]}
    commands = _commands(payload)

    assert expected_manager in managers
    assert runners["node_test_script"]["commands"] == [expected_command]
    assert expected_command in commands
    assert commands[expected_command]["surface"] == "javascript_typescript"
    assert commands[expected_command]["purpose"] == "test"
    assert commands[expected_command]["executes_untrusted_code"] is True
    assert commands[expected_command]["auto_run_allowed"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_preserves_npm_fallback_when_package_json_has_test_without_lockfile(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "node --test"}}),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _commands(payload)
    runners = {str(item["name"]): item for item in payload["test_runners"]}

    assert payload["package_managers"] == []
    assert runners["node_test_script"]["commands"] == ["npm test"]
    assert commands["npm test"]["auto_run_allowed"] is False
    assert commands["npm test"]["executes_untrusted_code"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
