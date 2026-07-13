from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _tools(payload: dict) -> dict[str, dict]:
    return {str(item["name"]): item for item in payload["security_tools"]}


def _commands(payload: dict) -> dict[str, dict]:
    return {str(item["command"]): item for item in payload["recommended_proof_commands"]}


@pytest.mark.parametrize(
    ("evidence_path", "content"),
    [
        (".github/workflows/security.yml", "steps:\n  - run: cargo audit\n"),
        ("Makefile", "audit:\n\tcargo audit\n"),
        (".cargo/audit.toml", "[advisories]\nignore = []\n"),
        ("audit.toml", "[advisories]\nignore = []\n"),
    ],
)
def test_adoption_surface_detects_explicit_cargo_audit_evidence(
    tmp_path: Path,
    evidence_path: str,
    content: str,
) -> None:
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    _write(tmp_path / evidence_path, content)

    payload = discover_adoption_surface(tmp_path)
    tools = _tools(payload)
    commands = _commands(payload)

    assert "cargo_audit" in tools
    assert set(tools["cargo_audit"]["evidence"]) == {evidence_path}
    assert tools["cargo_audit"]["confidence"] == "detected"
    assert "cargo audit" in commands
    assert commands["cargo audit"]["surface"] == "rust"
    assert commands["cargo audit"]["purpose"] == "security"
    assert commands["cargo audit"]["evidence"] == [evidence_path]
    assert commands["cargo audit"]["auto_run_allowed"] is False
    assert commands["cargo audit"]["executes_untrusted_code"] is True
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_surface_does_not_infer_cargo_audit_from_cargo_manifest_alone(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "Cargo.toml", "[package]\nname = 'demo'\nversion = '0.1.0'\n")
    _write(tmp_path / "Cargo.lock", "version = 3\n")

    payload = discover_adoption_surface(tmp_path)

    assert "cargo_audit" not in _tools(payload)
    assert "cargo audit" not in _commands(payload)
    assert "cargo test" in _commands(payload)


def test_adoption_surface_ignores_cargo_audit_text_without_rust_manifest(
    tmp_path: Path,
) -> None:
    _write(tmp_path / ".github/workflows/security.yml", "steps:\n  - run: cargo audit\n")

    payload = discover_adoption_surface(tmp_path)

    assert "cargo_audit" not in _tools(payload)
    assert "cargo audit" not in _commands(payload)
