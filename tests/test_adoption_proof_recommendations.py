from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_proof_recommendations import (
    SCHEMA_VERSION,
    build_proof_recommendations_payload,
    render_proof_recommendations_text,
    write_proof_recommendations_artifact,
)
from sdetkit.adoption_surface import (
    discover_adoption_surface,
    write_adoption_surface_artifact,
)


def test_proof_recommendations_classify_current_repo_commands() -> None:
    payload = build_proof_recommendations_payload(Path("."))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["summary"]["recommended_next_action"] == "review_and_run_manual_proof"
    assert payload["summary"]["first_manual_command"]
    assert payload["summary"]["required_count"] >= 1
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False

    commands = {item["command"]: item for item in payload["proof_recommendations"]}
    assert "python -m pytest -q -o addopts=" in commands
    assert commands["python -m pytest -q -o addopts="]["operator_level"] == "required"
    assert commands["python -m pytest -q -o addopts="]["confidence"] == "high"
    assert commands["python -m pytest -q -o addopts="]["execution_policy"] == "manual_only"
    assert payload["summary"]["confidence_counts"]["high"] >= 1
    assert commands["python -m pytest -q -o addopts="]["auto_run_allowed"] is False
    assert all(item["manual_execution_required"] is True for item in commands.values())


def test_proof_recommendations_preserve_source_confidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pytest"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements-test.txt").write_text(
        "pytest==9.1.1\n",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "confidence-fixture",
                "scripts": {"test": "vitest run"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")

    surface = discover_adoption_surface(tmp_path)
    payload = build_proof_recommendations_payload(
        tmp_path,
        surface_payload=surface,
    )
    commands = {item["command"]: item for item in payload["proof_recommendations"]}

    assert commands["python -m pytest -q -o addopts="]["confidence"] == "high"
    assert commands["npm test"]["confidence"] == "medium"
    assert payload["summary"]["confidence_counts"] == {
        "high": 1,
        "medium": 1,
        "low": 0,
        "unknown": 0,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_proof_recommendations_normalize_missing_or_invalid_confidence(
    tmp_path: Path,
) -> None:
    surface = discover_adoption_surface(tmp_path)
    surface["recommended_proof_commands"] = [
        {
            "surface": "custom",
            "command": "custom proof",
            "purpose": "test",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
        },
        {
            "surface": "custom",
            "command": "another proof",
            "confidence": "UNTRUSTED",
            "purpose": "quality",
            "executes_untrusted_code": True,
            "auto_run_allowed": False,
        },
    ]

    payload = build_proof_recommendations_payload(
        tmp_path,
        surface_payload=surface,
    )

    assert [item["confidence"] for item in payload["proof_recommendations"]] == [
        "unknown",
        "unknown",
    ]
    assert payload["summary"]["confidence_counts"] == {
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 2,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_proof_recommendations_turn_unknowns_into_review_first_items() -> None:
    payload = build_proof_recommendations_payload(
        Path("tests/fixtures/adoption_repos/mixed_python_node")
    )

    assert payload["review_first_items"] == [
        {
            "description": "JavaScript/TypeScript package manifest detected but test command is not proven",
            "operator_level": "review_first",
            "manual_resolution_required": True,
            "auto_run_allowed": False,
            "reason": "unknown repo surface must be reviewed before proof execution",
        }
    ]
    assert payload["summary"]["review_first_count"] == 1


def test_proof_recommendations_cli_dispatch_writes_text_summary(
    tmp_path: Path,
    capsys,
) -> None:
    surface = tmp_path / "adoption-surface.json"
    out = tmp_path / "proof-recommendations.json"
    write_adoption_surface_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/mixed_python_node"),
        out=surface,
    )

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-proof-recommendations",
            "--root",
            ".",
            "--surface-json",
            str(surface),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "adoption_proof_recommendations_status=generated" in stdout
    assert "confidence=high" in stdout
    assert "confidence_counts=" in stdout
    assert "manual_only=true" in stdout
    assert "auto_run_allowed=false" in stdout
    assert "review_first_count=1" in stdout


def test_proof_recommendations_text_keeps_authority_boundary_visible() -> None:
    payload = build_proof_recommendations_payload(Path("."))
    text = render_proof_recommendations_text(payload)

    assert "authority_boundary:" in text
    assert "- automation_allowed=false" in text
    assert "- patch_application_allowed=false" in text
    assert "first_manual_command=" in text


def test_proof_recommendations_writer_records_json(tmp_path: Path) -> None:
    out = tmp_path / "proof-recommendations.json"

    payload = write_proof_recommendations_artifact(
        repo_root=Path("tests/fixtures/adoption_repos/python_pytest_github"),
        out=out,
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_self_learning_advances_after_proof_recommendations_exist() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "review learning gaps"
    assert "add proof command recommendation levels" not in payload["learning_gaps"]
    assert "add repo topology summary" not in payload["learning_gaps"]
    assert "add adoption evidence bundle" not in payload["learning_gaps"]
    assert "add public repo trial matrix" not in payload["learning_gaps"]
    assert "add public repo trial matrix report" not in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
