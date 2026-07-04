from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


@pytest.mark.parametrize(
    ("path", "content"),
    [
        (
            ".github/workflows/security.yml",
            "steps:\n  - run: govulncheck ./...\n",
        ),
        (
            "scripts/security.sh",
            "#!/usr/bin/env sh\nset -e\ngovulncheck ./...\n",
        ),
    ],
)
def test_adoption_surface_detects_govulncheck_security_surface_from_owned_evidence(
    tmp_path: Path,
    path: str,
    content: str,
) -> None:
    _write(tmp_path / "go.mod", "module example.com/demo\n")
    _write(tmp_path / path, content)

    payload = discover_adoption_surface(tmp_path)
    tools = {str(item["name"]): item for item in payload["security_tools"]}
    commands = _commands(payload)

    assert tools["govulncheck"]["confidence"] == "detected"
    assert tools["govulncheck"]["evidence"] == [path]
    assert "go test ./..." in commands
    assert commands["govulncheck ./..."]["surface"] == "go"
    assert commands["govulncheck ./..."]["purpose"] == "security"
    assert commands["govulncheck ./..."]["auto_run_allowed"] is False
    assert commands["govulncheck ./..."]["executes_untrusted_code"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_does_not_infer_govulncheck_from_go_mod_only(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "go.mod", "module example.com/demo\n")

    payload = discover_adoption_surface(tmp_path)
    tools = {str(item["name"]) for item in payload["security_tools"]}
    commands = _commands(payload)

    assert "govulncheck" not in tools
    assert "go test ./..." in commands
    assert "govulncheck ./..." not in commands
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
