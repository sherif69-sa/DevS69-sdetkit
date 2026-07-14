from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item for item in items if isinstance(item, dict) and item.get("name")
    }


def _commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"]): item
        for item in items
        if isinstance(item, dict) and item.get("command")
    }


def test_npm_audit_workflow_command_is_source_grounded(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest"}}),
    )
    _write(tmp_path / "package-lock.json", "{}\n")
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    command = "npm audit --audit-level=high --omit=dev"
    _write(workflow, f"jobs:\n  audit:\n    steps:\n      - run: {command}\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert security["npm_audit"]["evidence"] == [".github/workflows/security.yml"]
    assert command in commands
    assert commands[command]["purpose"] == "security"
    assert commands[command]["evidence"] == [".github/workflows/security.yml"]
    assert commands[command]["source"] == {
        "scope": "repository_command",
        "file": ".github/workflows/security.yml",
        "package_manager": "npm",
    }
    assert commands[command]["executes_untrusted_code"] is True
    assert commands[command]["auto_run_allowed"] is False
    assert "npm test" in commands
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_pnpm_audit_shell_command_preserves_exact_text(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest"}}),
    )
    _write(tmp_path / "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    command = "pnpm audit --prod --audit-level high"
    _write(tmp_path / "scripts" / "security.sh", f"#!/usr/bin/env sh\n{command}\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert security["pnpm_audit"]["evidence"] == ["scripts/security.sh"]
    assert commands[command]["source"] == {
        "scope": "repository_command",
        "file": "scripts/security.sh",
        "package_manager": "pnpm",
    }
    assert commands[command]["purpose"] == "security"
    assert commands[command]["auto_run_allowed"] is False


def test_nested_yarn_audit_package_script_preserves_workspace_context(tmp_path: Path) -> None:
    manifest = tmp_path / "apps" / "web" / "package.json"
    command = "yarn npm audit --all --recursive"
    _write(
        manifest,
        json.dumps(
            {
                "name": "web",
                "scripts": {
                    "test": "vitest",
                    "dependencies:audit": command,
                },
            }
        ),
    )
    _write(tmp_path / "apps" / "web" / "yarn.lock", "# yarn lock\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    commands = _commands(payload)

    assert security["yarn_audit"]["evidence"] == ["apps/web/package.json"]
    assert commands[command]["source"] == {
        "scope": "repository_command",
        "file": "apps/web/package.json",
        "package_manager": "yarn",
        "script": "dependencies:audit",
        "working_directory": "apps/web",
    }
    assert commands[command]["purpose"] == "security"
    assert commands[command]["executes_untrusted_code"] is True
    assert commands[command]["auto_run_allowed"] is False


def test_javascript_lockfiles_do_not_invent_security_proof(tmp_path: Path) -> None:
    _write(tmp_path / "package.json", json.dumps({"name": "demo"}))
    _write(tmp_path / "package-lock.json", "{}\n")
    _write(tmp_path / "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
    _write(tmp_path / "yarn.lock", "# yarn lock\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    security_commands = [
        item
        for item in payload["recommended_proof_commands"]
        if isinstance(item, dict)
        and item.get("surface") == "javascript_typescript"
        and item.get("purpose") == "security"
    ]

    assert "npm_audit" not in security
    assert "pnpm_audit" not in security
    assert "yarn_audit" not in security
    assert security_commands == []


def test_dynamic_and_mutating_javascript_audit_commands_are_review_first(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "package.json", json.dumps({"name": "demo"}))
    _write(tmp_path / "package-lock.json", "{}\n")
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    _write(
        workflow,
        "jobs:\n"
        "  audit:\n"
        "    steps:\n"
        '      - run: npm audit --audit-level="$AUDIT_LEVEL"\n'
        "      - run: pnpm audit --fix\n",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    security_commands = [
        item
        for item in payload["recommended_proof_commands"]
        if isinstance(item, dict) and item.get("purpose") == "security"
    ]

    assert "npm_audit" not in security
    assert "pnpm_audit" not in security
    assert security_commands == []
    assert (
        "JavaScript package security command for npm in .github/workflows/security.yml "
        "is dynamic and was not guessed" in payload["review_first_unknowns"]
    )
    assert (
        "JavaScript package security command for pnpm in .github/workflows/security.yml "
        "requests dependency mutation and was not recommended"
        in payload["review_first_unknowns"]
    )


def test_descriptive_or_echoed_audit_text_is_not_a_security_command(tmp_path: Path) -> None:
    _write(tmp_path / "package.json", json.dumps({"name": "demo"}))
    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    _write(
        workflow,
        "jobs:\n"
        "  audit:\n"
        "    steps:\n"
        "      - name: npm audit\n"
        '      - run: echo "npm audit"\n',
    )

    payload = discover_adoption_surface(tmp_path)

    assert "npm_audit" not in _named(payload["security_tools"])
    assert not any(
        isinstance(item, dict) and item.get("purpose") == "security"
        for item in payload["recommended_proof_commands"]
    )
    assert not any(
        "JavaScript package security command" in item
        for item in payload["review_first_unknowns"]
    )
